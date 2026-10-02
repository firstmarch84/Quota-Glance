import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import tkinter as tk
from unittest import TestCase, main
from unittest.mock import Mock, patch
from app import App


class AppViewsTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        for target,value in [('app.DATA',Path(self.directory.name)),('app.Tray',Mock()),
                             ('app.create_adapters',Mock(return_value={})),
                             ('app.startup.status',Mock(return_value={'enabled':False}))]:
            patcher = patch(target,value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = App()
        self.addCleanup(self.app.root.destroy)
        self.app.states['claude'].update(rows=[{'label':'현재 세션','remaining':98},
            {'label':'이번 주','remaining':73},{'kind':'resetCredit','label':'전체 초기화','resetText':'만료일: 10월 23일'}],
            updated=time.time(),error=None)
        self.app.render('claude')
        self.app.root.update_idletasks()

    def test_compact_toggle_and_stale(self):
        original = self.app.root.geometry()
        self.app.toggle_compact()
        self.app.root.update_idletasks()
        self.assertTrue(self.app.compact)
        self.assertTrue(json.loads(self.app.settings_path.read_text())['compact'])
        self.assertEqual(self.app.compact_frame.winfo_manager(),'pack')
        self.app.states['claude']['updated'] -= 160
        self.app.render_compact('claude')
        title = self.app.compact_widgets['claude']['box'].winfo_children()[0]
        self.assertIn('이전 수치',title.cget('text'))
        self.app.toggle_compact()
        self.app.root.update_idletasks()
        self.assertEqual(self.app.root.geometry(),original)
        self.assertFalse(self.app.compact)

    def test_picker_inventory_and_cancel_never_dispatches(self):
        bridge = Mock(start_error=None)
        bridge.credit_snapshot.return_value={'received':time.time(),'items':[
            {'label':'전체 재설정','detail':'10월 5일 만료','identity':'fixture','available':True}]}
        self.app.reset_bridge = bridge
        self.app.reset_picker('codex')
        popup = next(w for w in self.app.root.winfo_children() if isinstance(w,tk.Toplevel))
        def descendants(w):
            for child in w.winfo_children():
                yield child
                yield from descendants(child)
        from tkinter import ttk
        tree = next(w for w in descendants(popup) if isinstance(w,ttk.Treeview))
        self.assertEqual(len(tree.get_children()),1)
        tree.selection_set('0')
        button = next(w for w in descendants(popup) if isinstance(w,tk.Button) and w.cget('text')=='선택한 초기화권 사용')
        with patch('app.messagebox.askokcancel',return_value=False):
            button.invoke()
        bridge.reveal_credit.assert_not_called()
        self.assertFalse(any(isinstance(w,tk.Button) and w.cget('text')=='연결 코드 복사' for w in descendants(popup)))
        with patch('app.messagebox.askokcancel',return_value=True):
            button.invoke()
        bridge.reveal_credit.assert_called_once_with('codex','fixture',consume=True)


if __name__=='__main__':
    main()
