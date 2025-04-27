import unittest
from unittest import TestCase
from unittest.mock import patch, MagicMock
import sys
import os
from pathlib import Path
sys.path.append(os.path.abspath('C:\\Users\saphi\PycharmProjects\multipleye-preprocessing\quality-report'))
from data_collection import DataCollection

# the tests were written with github copilot, so they are not complete yet, and I don't know if they are correct, nor do I understand them fully



class TestDataCollection(TestCase):
    def test_add_recorded_sessions(self):

        self.fail()

    def test_convert_edf_to_asc(self):
        self.fail()
    def test_create_gaze_frame(self):
        self.fail()

    def test_get_gaze_frame(self):
        self.fail()

    def setUp(self):
        """ Set up the test environment,
            The setUp method initializes a DataCollection instance before each test.
            This ensures that each test starts with a fresh instance of the class.
        """

        self.data_collection = DataCollection(
                data_collection_name="TestCollection",
                stimulus_language="English",
                country="USA",
                year=2023,
                eye_tracker="EyeLink 1000 Plus"
            )

    @patch("os.scandir")
    def test_add_recorded_sessions(self, mock_scandir):
        """
        Purpose: Tests the add_recorded_sessions method.
        Mocking: Mocks the directory structure using os.scandir and pathlib.Path.glob to simulate session folders and files.
        Assertions: Verifies that the session is added correctly to the sessions dictionary with the expected file name.
        """
        # Mock the directory structure
        mock_dir = MagicMock()
        mock_dir.is_dir.return_value = True
        mock_dir.name = "session1"
        mock_dir.path = "/mock/path/session1"
        mock_scandir.return_value = [mock_dir]

        # Mock session file
        mock_file = MagicMock()
        mock_file.name = "test.edf"
        mock_file.path = "/mock/path/session1/test.edf"
        with patch("pathlib.Path.glob", return_value=[mock_file]):
            self.data_collection.add_recorded_sessions(data_root=Path("/mock/path"), session_folder_regex=".*")

        self.assertIn("session1", self.data_collection.sessions)
        self.assertEqual(self.data_collection.sessions["session1"]["session_file_name"], "test.edf")

    @patch("subprocess.run")
    @patch("pathlib.Path.with_suffix")
    def test_convert_edf_to_asc(self, mock_with_suffix, mock_subprocess_run):
        # Mock session data
        """
        Mocking:Mocks subprocess.run to simulate the external edf2asc command.
        Mocks pathlib.Path.with_suffix to simulate file path operations.
        Assertions: Ensures the edf2asc command is called with the correct arguments.
        """
        self.data_collection.sessions = {
            "session1": {
                "session_file_path": "/mock/path/session1/test.edf"
            }
        }
        mock_with_suffix.return_value.exists.return_value = False

        self.data_collection.convert_edf_to_asc()

        mock_subprocess_run.assert_called_with(["edf2asc", Path("/mock/path/session1/test.edf")])

    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("pickle.load")
    def test_get_gaze_frame(self, mock_pickle_load, mock_open):

        """
        Purpose: Tests the get_gaze_frame method.
        Mocking:
        Mocks builtins.open and pickle.load to simulate reading a gaze data file.
        Assertions: Verifies that the gaze data is loaded correctly and matches the mocked data.
        """
        # Mock session data
        self.data_collection.sessions = {
            "session1": {
                "gaze_path": "/mock/path/session1/gaze.pkl"
            }
        }
        mock_pickle_load.return_value = "mock_gaze_data"

        gaze_data = self.data_collection.get_gaze_frame(session_identifier="session1")

        mock_open.assert_called_with("/mock/path/session1/gaze.pkl", "rb")
        self.assertEqual(gaze_data, "mock_gaze_data")

    def test_get_gaze_frame_session_not_found(self):
        """
        Purpose: Tests the behavior of get_gaze_frame when the session identifier does not exist.
A       Assertions: Ensures a KeyError is raised for a nonexistent session

        """
        with self.assertRaises(KeyError):
            self.data_collection.get_gaze_frame(session_identifier="nonexistent_session")

if __name__ == "__main__":
    unittest.main()
