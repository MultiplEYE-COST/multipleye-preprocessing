from pathlib import Path
import zipfile
import os
import shutil
import polars as pl
from contextlib import contextmanager
import re

def main():
    #Place for verbose path to the data collection folder that should be cleaned.
    #Use only relative paths to everything else based on this folder.
    collection_folder = Path(r"C:\Users\anpopp\Documents\multipleye-preprocessing\data\MultiplEYE_SL_SI_Ljubljana_1_2025")

    #Dictionary for unzipping. Keys: Zip-files, Values: Directories to unzip to.
    unzip_dic = {
        #Path("relative_zip_path"):Path("relative_goal_directory"),        
    }

    #Dictionary for unnesting. Keys: Directories to be unnested, Values: Directories to unnest to
    unnest_dic = {
        #Path(r"00_oldFiles_toBeDeleted\pilot_sessions\002_SL_SI_1_ET1"):Path("00_oldFiles_toBeDeleted\pilot_sessions"),
    }

    #Dictionary for moving and renaming. Keys: Old Paths, Values: New Paths.
    move_rename_dic = {
        #Path("relative_old_path"):Path("relative_new_path"),
    }

    #Stim order versions csv to be edited and order version dic with version numbers and pids to be assigned
    stim_order_versions = Path("")
    order_version_dic = {
        #000(version_number):000(pid),
                         }

    #List for all paths to files and directories to be deleted.
    del_list = [
        #Path(r"tobedeleted"),
    ]

    psych_pid_reassignment = {
        #"000_lang_country_1_PT0":999,
        "000_SL_SI_1_PT0":999
    }





    with working_directory(collection_folder):
        print("="*20)
        print(f"Cleaning folder {os.getcwd()}")
        print("="*20)
        unzip_files(unzip_dic)
        move_rename_files(move_rename_dic)
        unnest(unnest_dic)
        edit_order_csv(stim_order_versions, order_version_dic)
        reassign_psych_pids(psych_pid_reassignment)
        del_files(del_list)

        #Space for further code to be executed in the folder.

        print("="*20)
        print(f"Done Cleaning")
        print("="*20)        


def unzip_files(unzip_dic: dict[Path, Path]) -> None:
    for zip_path, goal_dir in unzip_dic.items():
        if zip_path.exists() and goal_dir.exists():
            with zipfile.ZipFile(zip_path, "r") as zip_arch:
                zip_arch.extractall(unzip_dic[zip_path])

            os.remove(zip_path)
        else:
            print(f"No file found at {zip_path} or no directory found at {goal_dir}. Skipping.")
            continue

    return None

def move_rename_files(move_dic: dict[Path, Path]) -> None:
    for old_path, new_path in move_dic.items():
        if old_path.exists():
            os.rename(old_path, new_path)
        else:
            print(f"No file found at {old_path}. Skipping.")
            continue

    return None

def del_files(del_list: list[Path]) -> None:
    '''Deletes files and folders as well as their contents
    '''
    for del_path in del_list:
        if del_path.exists():
            if del_path.is_dir():
                shutil.rmtree(del_path)
            else:
                os.remove(del_path)
        else:
            print(f"No file found at {del_path}. Skipping.")
            continue

    return None

def unnest(to_unnest: dict[Path, Path]) -> None:
    for unwanted_dir, goal_dir in to_unnest.items():
        if unwanted_dir.exists() and goal_dir.exists():
            for thing in os.listdir(unwanted_dir):
                old_path = unwanted_dir.joinpath(thing)
                new_path = goal_dir.joinpath(thing)
                os.rename(old_path, new_path)

            shutil.rmtree(unwanted_dir)
            
        else:
            print(f"No directory found at {unwanted_dir} or no directory found at {goal_dir}. Skipping.")
            continue

    return None


def edit_order_csv(
        file_path: Path,
        order_dict: dict[int, int],
) -> None:
    if len(order_dict) == 0:
        return None
    
    if file_path.exists():
        df = pl.read_csv(file_path)
        for order_version, pid in order_dict.items():
            if order_version not in df["version_number"]:
                print(f"Version {order_version} does not exist in order version csv. Skipping.")
                continue
            df = df.with_columns(
                pl.when(pl.col("version_number") == order_version)
                .then(pid)
                .alias("participant_id")
            )
                
    else:
        print(f"No file found at {file_path}. Not editing order file.")

    return None

def reassign_psych_pids(reassignment: dict[str, int]) -> None:
    test_folder = Path("psychometric-tests-sessions")
    if test_folder.exists():
        for session_name, new_pid in reassignment.items():
            if not re.match(r"^\d\d\d",session_name):
                print(f"{session_name} is not a valid session name. Skipping.")
                continue
            old_pid = int(session_name[:3])
            print(old_pid)
            session_path = test_folder.joinpath(session_name)
            if session_path.exists():
                #TODO
                continue
            else:
                print(f"No session folder at {session_path}. Skipping")
                continue
        return None
    else:
        print(f"No folder at {test_folder}. Not editing psychometric files")

@contextmanager
def working_directory(directory):
    owd = os.getcwd()
    try:
        os.chdir(directory)
        yield directory
    finally:
        os.chdir(owd)

if __name__ == "__main__":
    main()