# bridge/file_ops.py
# FileOpsMixin：负责题库文件的加载与保存（JSON / Excel），以及路径 / URI 适配。
# 该 Mixin 通过 self._read_android_uri / self._open_android_uri_for_write
# 动态派发到 AndroidStorageMixin，不直接引用该 Mixin。

import io
import os
from contextlib import contextmanager

from PySide6.QtCore import QFile, QIODevice, QUrl, Signal, Slot

from platform_utils import is_android


class FileOpsMixin:
    """文件操作 Mixin：加载、保存、路径解析"""

    # ---------- 信号 ----------
    qmlFileDialogRequested = Signal()

    # ---------- 初始化钩子 ----------
    def _init_file_ops(self):
        """由主类显式调用，当前无额外状态"""
        pass

    # ==============================================================
    # 路径 / URI 适配
    # ==============================================================
    def _resolve_read(self, raw):
        if not raw:
            return None, None

        if raw.startswith("file://"):
            local = QUrl(raw).toLocalFile()
            return (local, local) if local and os.path.exists(local) else (None, None)

        if len(raw) > 2 and raw[0] == "/" and raw[2] == ":":
            raw = raw[1:]

        if "://" not in raw:
            return (raw, raw) if os.path.exists(raw) else (None, None)

        if raw.startswith("content://"):
            if not is_android():
                return None, None
            try:
                data = self._read_android_uri(raw)
                if data is None:
                    return None, None
                return io.BytesIO(data), raw
            except Exception as e:
                print("[content://] read failed: {}".format(e))
                return None, None

        qf = QFile(QUrl(raw))
        if not qf.open(QIODevice.ReadOnly):
            return None, None
        try:
            return io.BytesIO(bytes(qf.readAll())), raw
        finally:
            qf.close()

    @contextmanager
    def _resolve_write(self, raw):
        if not raw:
            yield None, None
            return

        if raw.startswith("file://"):
            raw = QUrl(raw).toLocalFile() or raw

        if len(raw) > 2 and raw[0] == "/" and raw[2] == ":":
            raw = raw[1:]

        if "://" not in raw:
            yield raw, raw
            return

        if raw.startswith("content://"):
            if not is_android():
                yield None, None
                return
            writer = None
            try:
                writer = self._open_android_uri_for_write(raw)
                yield writer, raw
            except Exception as e:
                print("[content://] open for write failed: {}".format(e))
                yield None, None
            finally:
                if writer is not None:
                    try:
                        writer.close()
                    except Exception:
                        pass
            return

        qf = QFile(QUrl(raw))
        if not qf.open(QIODevice.WriteOnly | QIODevice.Truncate):
            yield None, None
            return
        try:
            yield qf, raw
        finally:
            qf.close()

    # ==============================================================
    # 文件操作
    # ==============================================================
    @Slot(str, result=int)
    def loadJsonFile(self, path):
        return self.loadFromJson(path)

    @Slot(str, result=int)
    def loadFromJson(self, raw):
        source, resolved = self._resolve_read(raw)
        if source is None:
            self.errorOccurred.emit(
                "无法读取所选文件。\n\n"
                "请确认文件存在且为有效的 JSON 格式。"
            )
            return 0

        try:
            count = self._controller.load_from_json_file(source)
        except Exception as e:
            self.errorOccurred.emit("打开失败：{}".format(e))
            return 0

        if count > 0:
            self._controller.current_file_path = resolved
            self._controller.is_modified = False

        self._refresh()
        if count == 0:
            self.errorOccurred.emit("该文件不包含有效题目数据")
        else:
            self.infoMessage.emit("已打开题库，共 {} 道题".format(count))
        return count

    @Slot(str, result=int)
    def loadFromExcel(self, raw):
        if is_android():
            self.errorOccurred.emit("Android 端不支持 Excel 导入，请使用 JSON 格式的题库。")
            return 0

        source, _ = self._resolve_read(raw)
        if source is None:
            self.errorOccurred.emit("无法读取所选文件")
            return 0

        try:
            count = self._controller.load_from_excel_file(source)
        except Exception as e:
            self.errorOccurred.emit(
                "导入失败：{}\n\n"
                "Android 端通常不支持 Excel，请先在桌面端转为 JSON。".format(e)
            )
            return 0

        if count > 0:
            self._controller.current_file_path = None
            self._controller.is_modified = True

        self._refresh()
        if count == 0:
            self.errorOccurred.emit("Excel 文件中没有有效题目")
        else:
            self.infoMessage.emit("已从 Excel 导入 {} 道题，请记得保存".format(count))
        return count

    @Slot(str, result=bool)
    def saveToFile(self, raw):
        if not self._controller.has_questions():
            self.errorOccurred.emit("没有可保存的数据")
            return False

        with self._resolve_write(raw) as pair:
            target, resolved = pair
            if target is None:
                self.errorOccurred.emit("保存失败：无法写入所选位置")
                return False
            try:
                self._controller.save_to_file(target)
            except Exception as e:
                self.errorOccurred.emit("保存失败：{}".format(e))
                return False

        self._controller.current_file_path = resolved
        self._controller.is_modified = False
        self._refresh()
        self.infoMessage.emit("已保存")
        return True

    @Slot(result=bool)
    def saveCurrent(self):
        path = self._controller.current_file_path
        if not self._controller.has_questions() or not path:
            return False
        return self.saveToFile(path)
