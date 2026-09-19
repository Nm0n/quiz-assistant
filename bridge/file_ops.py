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
            # Qt 6.5+ 的 QFile 支持直接打开 content:// URI，无需 jnius
            qf = QFile(QUrl(raw))
            if not qf.open(QIODevice.ReadOnly):
                print("[content://] QFile open failed for: {}".format(raw))
                return None, None
            try:
                return io.BytesIO(bytes(qf.readAll())), raw
            finally:
                qf.close()

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
            # 把导入的文件复制到应用私有目录（如果还不在那里）
            final_path = self._import_to_private_dir(resolved)
            self._controller.current_file_path = final_path
            self._controller.is_modified = False

        self._refresh()
        if count == 0:
            self.errorOccurred.emit("该文件不包含有效题目数据")
        else:
            self.infoMessage.emit("已打开题库，共 {} 道题".format(count))
        return count

    def _import_to_private_dir(self, source_path):
        """
        把用户选中的文件复制到应用私有题库目录，返回最终的目标路径。
        如果来源已经在私有目录内，或者复制失败，返回原路径。
        """
        import datetime

        if not source_path:
            return None

        watch_dir = self._get_watch_dir()

        # 已经在私有目录里，不需要复制
        if source_path.startswith(watch_dir):
            return source_path

        # 生成目标文件名
        base_name = self._basename(source_path)
        if (not base_name or base_name == "未命名"
                or not base_name.lower().endswith(".json")):
            base_name = "题库_{}.json".format(
                datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            )

        # 避免重名
        target_path = os.path.join(watch_dir, base_name)
        counter = 1
        while os.path.exists(target_path):
            name, ext = os.path.splitext(base_name)
            target_path = os.path.join(
                watch_dir, "{}_{}{}".format(name, counter, ext)
            )
            counter += 1

        try:
            # 用 controller 的 save_to_file 把当前 engine 的内容写到 target
            self._controller.save_to_file(target_path)
        except Exception as e:
            print("[_import_to_private_dir] failed: {}".format(e))
            return source_path

        return target_path

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

    # ==============================================================
    # Android 文件选择器回调处理（保留，供未来使用）
    # ==============================================================
    def _process_imported_bytes(self, data, name):
        """
        接收 Android 文件选择器返回的字节数据，写入私有目录后加载。
        由 AndroidStorageMixin._on_activity_result 动态派发调用。
        """
        import datetime

        if not data:
            self.errorOccurred.emit("文件内容为空")
            return

        # 生成安全的目标文件名
        if not name or not name.lower().endswith(".json"):
            name = "题库_{}.json".format(
                datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            )

        watch_dir = self._get_watch_dir()
        target_path = os.path.join(watch_dir, name)
        counter = 1
        while os.path.exists(target_path):
            stem, ext = os.path.splitext(name)
            target_path = os.path.join(
                watch_dir, "{}_{}{}".format(stem, counter, ext)
            )
            counter += 1

        try:
            with open(target_path, "wb") as f:
                f.write(data)
            print("[_process_imported_bytes] saved to {}".format(target_path))
        except Exception as e:
            self.errorOccurred.emit("保存导入文件失败：{}".format(e))
            return

        # 直接从私有目录加载
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                count = self._controller.load_from_json_file(f)
        except Exception as e:
            self.errorOccurred.emit("加载失败：{}".format(e))
            return

        if count > 0:
            self._controller.current_file_path = target_path
            self._controller.is_modified = False

        self._refresh()
        if count == 0:
            self.errorOccurred.emit("该文件不包含有效题目数据")
        else:
            self.infoMessage.emit("已打开题库，共 {} 道题".format(count))

    # ==============================================================
    # 从剪贴板导入题库（新建 / 替换）
    # ==============================================================
    @Slot(result=int)
    def importFromClipboard(self):
        """
        从系统剪贴板读取 JSON 文本并导入为题库。
        用户操作：在文件管理器里打开 JSON → 全选复制 → 回到应用点此按钮。
        """
        try:
            from PySide6.QtGui import QGuiApplication
            cb = QGuiApplication.clipboard()
            if cb is None:
                self.errorOccurred.emit("无法访问剪贴板")
                return 0
            text = cb.text()
        except Exception as e:
            self.errorOccurred.emit("读取剪贴板失败：{}".format(e))
            return 0

        if not text or not text.strip():
            self.errorOccurred.emit(
                "剪贴板为空。\n\n"
                "请先用手机的「文件管理」打开 JSON 文件，"
                "全选内容并复制，再回到应用点击此菜单。"
            )
            return 0

        return self._import_json_text(text, source_name="clipboard")

    @Slot(str, result=int)
    def importFromText(self, text):
        """从传入的文本导入 JSON 题库（供将来可能的 UI 调用）。"""
        return self._import_json_text(text, source_name="manual")

    def _import_json_text(self, text, source_name="imported"):
        """
        解析 JSON 文本，保存到应用私有目录并加载。
        返回成功加载的题目数量；失败返回 0。
        """
        import json
        import datetime

        if not text or not text.strip():
            self.errorOccurred.emit("内容为空")
            return 0

        # 清理 BOM 和前后空白
        if text.startswith("\ufeff"):
            text = text[1:]
        text = text.strip()

        # 先验证 JSON 是否有效
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            self.errorOccurred.emit(
                "JSON 格式错误：{}\n\n"
                "请确认复制了完整的文件内容（从第一个 [ 到最后一个 ]）。".format(e)
            )
            return 0

        if not isinstance(parsed, list):
            self.errorOccurred.emit(
                "JSON 格式不正确：顶层应该是数组（[]）。\n"
                "请确认复制的是题库文件本身，而不是其他内容。"
            )
            return 0

        if len(parsed) == 0:
            self.errorOccurred.emit("JSON 数组为空，没有题目。")
            return 0

        # 生成目标路径
        watch_dir = self._get_watch_dir()
        name = "题库_{}_{}.json".format(
            source_name,
            datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
        )
        target_path = os.path.join(watch_dir, name)

        # 规范化保存（重新序列化，统一格式）
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.errorOccurred.emit("保存导入文件失败：{}".format(e))
            return 0

        # 加载
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                count = self._controller.load_from_json_file(f)
        except Exception as e:
            self.errorOccurred.emit("加载失败：{}".format(e))
            return 0

        if count > 0:
            self._controller.current_file_path = target_path
            self._controller.is_modified = False

        self._refresh()
        if count == 0:
            self.errorOccurred.emit(
                "该文件不包含有效题目数据。\n\n"
                "请确认 JSON 里的题目字段（type / stem / options / answer）格式正确。"
            )
        else:
            self.infoMessage.emit("已导入 {} 道题".format(count))
        return count

    # ==============================================================
    # 从剪贴板追加题目（增量导入）
    # ==============================================================
    @Slot(result=int)
    def appendFromClipboard(self):
        """
        从系统剪贴板读取 JSON 文本，追加到当前题库（按题目 id 去重）。
        用于分多次导入大题库：每次粘贴一部分。
        """
        try:
            from PySide6.QtGui import QGuiApplication
            cb = QGuiApplication.clipboard()
            if cb is None:
                self.errorOccurred.emit("无法访问剪贴板")
                return -1
            text = cb.text()
        except Exception as e:
            self.errorOccurred.emit("读取剪贴板失败：{}".format(e))
            return -1

        if not text or not text.strip():
            self.errorOccurred.emit(
                "剪贴板为空。\n\n"
                "请先用手机的「文件管理」打开 JSON 文件，"
                "全选内容并复制，再回到应用点击此菜单。"
            )
            return -1

        return self._append_json_text(text)

    def _append_json_text(self, text):
        """
        解析 JSON 文本，按 id 去重后追加到当前题库，保存并重新加载。
        返回本次新增的题目数量；失败返回 -1。
        """
        import json
        import datetime

        if not text or not text.strip():
            self.errorOccurred.emit("内容为空")
            return -1

        if text.startswith("\ufeff"):
            text = text[1:]
        text = text.strip()

        # 解析 JSON 语法
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            self.errorOccurred.emit(
                "JSON 格式错误：{}\n\n"
                "请确认复制了完整的文件内容（从第一个 [ 到最后一个 ]）。".format(e)
            )
            return -1

        if not isinstance(parsed, list):
            self.errorOccurred.emit("JSON 格式不正确：顶层应该是数组（[]）。")
            return -1

        if len(parsed) == 0:
            self.errorOccurred.emit("JSON 数组为空，没有题目。")
            return -1

        # 用 DataManager 解析为 Question 对象（复用已有逻辑，保证字段兼容）
        try:
            new_questions = self._controller.data_manager.load_from_json_file(
                io.BytesIO(text.encode("utf-8"))
            )
        except Exception as e:
            self.errorOccurred.emit("解析题库失败：{}".format(e))
            return -1

        if not new_questions:
            self.errorOccurred.emit("没有解析到有效题目。")
            return -1

        # 拿到现有 master_list（可能为 None，表示当前没有题库）
        existing = []
        if self._controller.engine and self._controller.engine.master_list:
            existing = self._controller.engine.master_list

        existing_ids = {q.id for q in existing}
        added = [q for q in new_questions if q.id not in existing_ids]

        if not added:
            self.infoMessage.emit(
                "本次没有新增题目（{} 道题已存在）。".format(len(new_questions))
            )
            return 0

        merged = list(existing) + added

        # 决定保存路径：优先复用当前文件，没有则新建
        target_path = self._controller.current_file_path
        if not target_path:
            watch_dir = self._get_watch_dir()
            target_path = os.path.join(
                watch_dir,
                "题库_{}.json".format(
                    datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                ),
            )

        # 保存合并后的完整题库
        try:
            self._controller.data_manager.save_to_json_file(target_path, merged)
        except Exception as e:
            self.errorOccurred.emit("保存失败：{}".format(e))
            return -1

        # 重新加载
        try:
            count = self._controller.load_from_json_file(target_path)
        except Exception as e:
            self.errorOccurred.emit("重新加载失败：{}".format(e))
            return -1

        self._refresh()
        self.infoMessage.emit(
            "本次新增 {} 道题，题库共 {} 道题".format(len(added), count)
        )
        return len(added)
