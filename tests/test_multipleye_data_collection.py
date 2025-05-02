from unittest import TestCase
import pytest
import sys
import os
from pathlib import Path
sys.path.append(os.path.abspath('C:\\Users\saphi\PycharmProjects\multipleye-preprocessing\quality-report'))
from multipleye_data_collection import MultipleyeDataCollection
from unittest.mock import patch, MagicMock, mock_open
class TestMultipleyeDataCollection(TestCase):
    def setUp(self):
        # Set up the test environment
        # This is a placeholder for any setup you might need
        # For example, you could create a temporary directory or file
        # self.test_dir = tempfile.TemporaryDirectory()

        self.this_repo = Path().resolve().parent

        self.data_collection_folder = 'MultiplEYE_toy_X_x_1_1'
        self.data_folder_path = self.this_repo / "tests" / self.data_collection_folder

    def test_create_from_data_folder(self):
        test_collection = MultipleyeDataCollection.create_from_data_folder(self.data_collection_folder,
                                                                                different_stimulus_names=True)

        self.assertEqual(test_collection.language, 'toy')
        self.assertEqual(test_collection.country, 'X')
        self.assertEqual(test_collection.year, 1)
        #print(test_collection.eye_tracker)
        self.assertEqual("eyelink", test_collection.eye_tracker)
        self.assertEqual("MultiplEYE_toy_X_x_1_1", test_collection.data_collection_name)
        self.assertEqual(test_collection.city, 'x')
        self.assertEqual(test_collection.lab_number, 1)
        self.assertEqual(len(test_collection.sessions), 1)


    def test_create_gaze_frame(self):
        self.fail()

    def test_get_gaze_frame(self):
        self.fail()

    def test_create_sanity_check_report(self):
        self.fail()
@pytest.fixture
def data_collection():
    """
    Create a DataCollection instance for testing.
    :return: DataCollection instance
    """
    return MultipleyeDataCollection(
        config_file={},
        data_root=Path("/fake"),
        lab_configuration={},
        data_collection_name="TestCollection",
        stimulus_dir= Path("/fake/stim"),
        city="x",
        lab_number=1,
        session_folder_regex="",
        stimulus_language="English",
        country="US",
        year=2023,
        eye_tracker="EyeLink 1000 Plus"
    )
@patch("multipleye_data_collection.load_data")
@patch("multipleye_data_collection.preprocess")
@patch("builtins.open", new_callable=mock_open)
@patch("pickle.dump")
def test_create_gaze_frame(mock_pickle, mock_open_file, mock_preprocess, mock_load_data, data_collection):
    mock_gaze = MagicMock()
    mock_load_data.return_value = mock_gaze

    # Setup test instance

    data_collection.output_dir = Path("/fake/output")
    data_collection.data_root = Path("/fake/data")
    data_collection.lab_configuration = {}  # or whatever is needed

    session_name = "s01"
    data_collection.sessions = {
        session_name: {
            'asc_path': "/fake/asc/path.as"
                        "c"
        }
    }

    # Mock _get_sessions_name to return the session we want to test
    data_collection._get_session_names = MagicMock(return_value=[session_name])

    # Patch Path.exists to simulate that the file does NOT exist
    with patch.object(Path, "exists", return_value=False), \
         patch.object(Path, "mkdir"):

        data_collection.create_gaze_frame(session=session_name)

    # Assert that load_data and preprocess were called
    mock_load_data.assert_called_once()
    mock_preprocess.assert_called_once_with(mock_gaze)
    mock_pickle.assert_called_once()  # gaze should be dumped
