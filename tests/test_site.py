import unittest
from unittest.mock import Mock, patch

from emart24.site import advance, group_grid_cells, handle_login_dialog


class LoginDialogs(unittest.TestCase):
    def test_page_scroll_reset_is_not_navigation(self):
        link = Mock()
        link.is_visible.return_value = True
        link.is_enabled.return_value = True
        link.get_attribute.side_effect = lambda name: 'linkPage(2); return false;' if name == 'onclick' else None
        frame = Mock()
        frame.get_by_role.return_value.all.return_value = [link]
        page = Mock(frames=[frame])
        with patch('emart24.site.signature', side_effect=[(1,2), (31,32)]):
            self.assertTrue(advance(page, 1, '다음', {1,2,3}))
        page.wait_for_timeout.assert_called_once_with(100)

    def test_last_page_self_link_terminates(self):
        link = Mock()
        link.is_visible.return_value = True
        link.is_enabled.return_value = True
        link.get_attribute.side_effect = lambda name: 'linkPage(157); return false;' if name == 'onclick' else None
        frame = Mock()
        frame.get_by_role.return_value.all.return_value = [link]
        page = Mock(frames=[frame])
        self.assertFalse(advance(page,157,'다음',{1,2}))
        link.click.assert_not_called()

    def test_grid_with_trailing_blank_column(self):
        values = ["2819173", "10월 07일 7F 주문정보(7F 이마트24) 전송", "주문정보", "order.xls", "73", "0", "0", "0", "2026-10-07 10:42:58", "\u00a0"]
        cells = [{"holder":"grid", "top":29.5, "left":i*60, "index":i,"text":v} for i,v in enumerate(values)]
        result = group_grid_cells(list(reversed(cells)))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0].number, 2819173)
        self.assertEqual(result[0][1], 3)
        self.assertEqual(group_grid_cells(cells[:4]), [])

    def test_known_reconnect_confirmation(self):
        dialog = Mock(type="confirm", message="이미 로그인되어있습니다.다시 접속하시겠습니까?")
        blocked = []
        handle_login_dialog(dialog, blocked)
        dialog.accept.assert_called_once()
        dialog.dismiss.assert_not_called()
        self.assertEqual(blocked, [])

    def test_unknown_confirmation_is_not_accepted(self):
        dialog = Mock(type="confirm", message="비밀번호를 변경하시겠습니까?")
        blocked = []
        handle_login_dialog(dialog, blocked)
        dialog.accept.assert_not_called()
        dialog.dismiss.assert_called_once()
        self.assertEqual(blocked, ["confirm"])

    def test_alert_blocks_login(self):
        dialog = Mock(type="alert", message="로그인 실패")
        blocked = []
        handle_login_dialog(dialog, blocked)
        self.assertEqual(blocked, ["alert"])
        dialog.accept.assert_not_called()


if __name__ == "__main__":
    unittest.main()
