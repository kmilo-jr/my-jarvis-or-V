import sqlite3
import tempfile
import unittest
from pathlib import Path
from windows_notification_reader import WindowsPhoneNotificationReader


class WindowsNotificationsTests(unittest.TestCase):
    def test_desktop_and_phone_link_new_toasts_only_and_readonly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'notifications.db'
            con = sqlite3.connect(path)
            con.executescript('''CREATE TABLE NotificationHandler (RecordId INTEGER, PrimaryId TEXT);
                CREATE TABLE Notification (Id INTEGER, HandlerId INTEGER, Payload TEXT);
                INSERT INTO NotificationHandler VALUES (1, '5319275A.WhatsAppDesktop_test!App');
                INSERT INTO NotificationHandler VALUES (2, 'Microsoft.YourPhone_test!App');
                INSERT INTO NotificationHandler VALUES (3, 'Calendar');
                INSERT INTO Notification VALUES (1, 1, '<toast><text>Old</text></toast>');''')
            con.commit()
            reader = WindowsPhoneNotificationReader(); reader.path = path
            self.assertEqual(reader.poll_new(), [])
            con.executemany('INSERT INTO Notification VALUES (?, ?, ?)', [
                (2, 1, '<toast><text>Ana</text><text>Olá</text></toast>'),
                (3, 2, '<toast><text>WhatsApp</text><text>Bia</text><text>Oi</text></toast>'),
                (4, 3, '<toast><text>Appointment</text></toast>')])
            con.commit()
            before = path.read_bytes()
            items = reader.poll_new()
            self.assertEqual([x['source'] for x in items], ['windows-desktop', 'windows-phone-link'])
            self.assertEqual([x['title'] for x in items], ['Ana', 'Bia'])
            self.assertEqual(reader.poll_new(), [])
            self.assertEqual(before, path.read_bytes())
            con.close()


if __name__ == '__main__':
    unittest.main()
