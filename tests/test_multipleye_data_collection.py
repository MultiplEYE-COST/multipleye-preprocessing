from unittest import TestCase
import sys
import os
from pathlib import Path
sys.path.append(os.path.abspath('C:\\Users\saphi\PycharmProjects\multipleye-preprocessing\quality-report'))
from multipleye_data_collection import MultipleyeDataCollection

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
