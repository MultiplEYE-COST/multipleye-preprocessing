import os
import shutil
from contextlib import contextmanager
from pathlib import Path

import polars as pl


def main():
    # Place for verbose path to the data collection folder that should be cleaned.
    # Use only relative paths to everything else based on this folder.
    collection_folder = Path(
        r"/data/multipleye-preprocessing/data/PATH_TO_YOUR_COLLECTION"
    )

    # Please comment for everything you do here, why you do it, and where you got the information (e.g. session documentation sheet)

    # CONTAINERS FOR ALL ITEMS MENT FOR COMMON OPERATIONS
    # Dictionary for unzipping. Keys: Zip-files, Values: Directories to unzip to.
    # Session archives must be unpacked here: the pipeline expects unzipped
    # session folders and no longer extracts archives itself.
    unzip_dic = {
        # Path("relative_zip_path"):Path("relative_goal_directory"),  #COMMENT FOR DOCUMENTATION
        # Psychometric test exports may ship as a zip with a task-first layout.
        # Extract to a staging directory, rename the inner folder to core_data/
        # (see move_rename_dic), then restructure it into session-first folders
        # (see the extra-code block below). Archive and folder names are
        # collection-specific; keep them in the collection's copy of this script.
        # Path("psychometric-tests-sessions/<export>.zip"): Path("_extract_pt"),
    }

    # Dictionary for unnesting. Keys: Directories to be unnested, Values: Directories to unnest to
    unnest_dic = {
        # Path(r"path_to_unwanted_subfolder"):Path(r"path_to_where_to_unnest_to"), # COMMENT FOR DOCUMENTATION
    }

    # Dictionary for moving and renaming. Keys: Old Paths, Values: New Paths.
    move_rename_dic = {
        # Path("relative_old_path"):Path("relative_new_path"),   #COMMENT FOR DOCUMENTATION
        # Path("_extract_pt/<inner_folder>"): Path("psychometric-tests-sessions/core_data"),
    }

    # Stim order versions csv to be edited and order version dic with version numbers and pids to be assigned. Keys: version numbers, Values: what to write into the participant_id column
    stim_order_versions = Path("")
    order_version_dic = {
        # 000(version_number):000(pid),  #COMMENT FOR DOCUMENTATION
    }

    # List for all paths to files and directories to be deleted.
    del_list = [
        # Path(r"tobedeleted"),  #COMMENT FOR DOCUMENTATION
        # Path("_extract_pt"),
    ]

    # Recursively delete hidden files/directories (names starting with "."),
    # e.g. .DS_Store and .localized left behind by macOS/Windows. Runs inside
    # the collection folder only. Set to False to keep them.
    del_hidden = True

    # Change pids for psychometric test sessions to match the eyetracking counterpart for the same participant
    # Note that this can only be done after uncommenting the code below to restructure the psychometric folder
    # pid_dict = {
    # "CURRENT_PSYCH_SESSION_ID": new_id,
    # "XXX_ZH_CN_1_PT1": 000, #COMMENT FOR DOCUMENTATION
    # }

    # EXECUTION OF COMMON OPERATIONS AND SPACE FOR EXTRA FREE CODE
    with working_directory(collection_folder):
        # Here all code can be written to be executed directly in the target folder
        # All functions will ignore files that cannot be found, so the code can be executed multiple times, even if e.g. an unwanted file has already been deleted.
        print("=" * 60)
        print(f"Cleaning folder {os.getcwd()}")
        print("=" * 60)
        # unzip_files does not create its target directory. If you use a staging
        # directory in unzip_dic, create it before unpacking:
        # Path("_extract_pt").mkdir(exist_ok=True)
        unzip_files(unzip_dic)
        move_rename_files(move_rename_dic)
        unnest(unnest_dic)
        edit_order_csv(stim_order_versions, order_version_dic)
        del_files(del_list)
        if del_hidden:
            del_hidden_files()

        # Restructure a task-first psychometric-test export into session-first
        # folders. Uncomment and adapt after extracting the archive.
        # from preprocessing.scripts.restructure_psychometric_tests import (
        #     fix_psychometric_tests_structure,
        # )
        # fix_psychometric_tests_structure(
        #     config_folder=Path("psychometric-tests-sessions/participant_configs"),
        #     data_folder=Path("psychometric-tests-sessions/core_data"),
        #     out_folder=Path("psychometric-tests-sessions"),
        # )

        # Change pids for psychometric test sessions, Requires session-first psychometric folder structure
        # change_psychometric_pid(out_folder, pid_dict)

        # SPACE FOR FURTHER CODE TO BE EXECUTED IN THE FOLDER

        print("=" * 60)
        print("Done Cleaning")
        print("=" * 60)


def unzip_files(unzip_dic: dict[Path, Path]) -> None:
    if not unzip_dic:
        return
    print(f"Unpacking {len(unzip_dic)} archive(s)...")
    for archive_path, goal_dir in unzip_dic.items():
        if archive_path.exists() and goal_dir.exists():
            print(f"  Unpacking {archive_path} -> {goal_dir}")
            shutil.unpack_archive(str(archive_path), extract_dir=str(goal_dir))
            os.remove(archive_path)
            print(f"  Extracted and removed {archive_path.name}")
        else:
            print(
                f"  No file found at {archive_path} or no directory found at {goal_dir}. Skipping."
            )
            continue


def move_rename_files(move_dic: dict[Path, Path]) -> None:
    if not move_dic:
        return
    print(f"Renaming {len(move_dic)} path(s)...")
    for old_path, new_path in move_dic.items():
        if old_path.exists():
            print(f"  Renaming {old_path} -> {new_path}")
            os.rename(old_path, new_path)
        else:
            print(f"  No file found at {old_path}. Skipping.")
            continue


def del_files(del_list: list[Path]) -> None:
    """Deletes files and folders as well as their contents"""
    if not del_list:
        return
    print(f"Deleting {len(del_list)} path(s)...")
    for del_path in del_list:
        if del_path.exists():
            print(f"  Deleting {del_path}")
            if del_path.is_dir():
                shutil.rmtree(del_path)
            else:
                os.remove(del_path)
        else:
            print(f"  No file found at {del_path}. Skipping.")
            continue


def del_hidden_files(root: Path = Path(".")) -> None:
    """Recursively delete hidden files and directories (names starting with ".").

    Intended to run inside the collection folder. Equivalent to
    ``find . -name ".*" -delete`` plus removal of macOS ``__MACOSX``
    directories, deepest paths first.

    Prints a single summary count instead of one line per path. Some archives
    ship a hidden file next to every real file (for example macOS ``._*``
    AppleDouble files), so listing each path would flood the log.
    """
    hidden = list(root.rglob(".*")) + list(root.rglob("__MACOSX"))
    deleted = 0
    for path in sorted(hidden, key=lambda p: len(p.parts), reverse=True):
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            os.remove(path)
        deleted += 1
    if deleted:
        print(f"Deleted {deleted} hidden files/directories.")


def unnest(to_unnest: dict[Path, Path]) -> None:
    if not to_unnest:
        return
    print(f"Unnesting {len(to_unnest)} directory(ies)...")
    for unwanted_dir, goal_dir in to_unnest.items():
        if unwanted_dir.exists() and goal_dir.exists():
            print(f"  Unnesting {unwanted_dir} into {goal_dir}")
            for thing in os.listdir(unwanted_dir):
                old_path = unwanted_dir.joinpath(thing)
                new_path = goal_dir.joinpath(thing)
                os.rename(old_path, new_path)

            shutil.rmtree(unwanted_dir)

        else:
            print(
                f"  No directory found at {unwanted_dir} or no directory found at {goal_dir}. Skipping."
            )
            continue


def edit_order_csv(
    file_path: Path,
    order_dict: dict[int, int],
) -> None:
    if len(order_dict) == 0:
        return

    if file_path.exists():
        print(
            f"Editing order version CSV {file_path} ({len(order_dict)} version(s))..."
        )
        df = pl.read_csv(file_path)
        for order_version, pid in order_dict.items():
            if order_version not in df["version_number"]:
                print(
                    f"  Version {order_version} does not exist in order version csv. Skipping."
                )
                continue
            print(f"  Version {order_version} -> participant_id {pid}")
            df = df.with_columns(
                pl.when(pl.col("version_number") == order_version)
                .then(pid)
                .otherwise(pl.col("participant_id"))
                .alias("participant_id")
            )
        df.write_csv(file_path)

    else:
        print(f"No file found at {file_path}. Not editing order file.")

    return


def _change_pid_in_csv(file: Path, new_pid: int):
    df = pl.read_csv(file)
    if "participant_id" in df:
        df = df.with_columns(pl.lit(new_pid).alias("participant_id"))
    elif "Participant_id" in df:
        df = df.with_columns(pl.lit(new_pid).alias("Participant_id"))
    else:
        print(f"Column [pP]articipant_id not found in {file}. Please check.")

    df.write_csv(file)


def change_psychometric_pid(psych_path: Path, input_dict: dict):
    print(f"Changing PIDs for {len(input_dict)} psychometric sessions")
    if not psych_path.exists():
        print(f"No folder at {psych_path}. Not editing psychometric sessions.")
        return
    for session_id, new_pid in input_dict.items():
        print(f"Changing PID for {session_id} to {new_pid}")
        old_pid = int(session_id[:3])
        lang = session_id[4:6]
        country = session_id[7:9]
        lab_no = int(session_id[10])
        subfolder = psych_path / session_id

        if not subfolder.exists():
            print(f"No session folder at {subfolder}. Skipping")
            continue

        filename_mappings = {
            f"{old_pid:03d}_{lang}_{country}": f"{new_pid:03d}_{lang}_{country}",
            f"{lang}{country}{lab_no}_{old_pid:03d}": f"{lang}{country}{lab_no}_{new_pid:03d}",
            f"{lang}{country}{lab_no}_{old_pid}_": f"{lang}{country}{lab_no}_{new_pid}_",
            f"SSTM-{old_pid}.dat": f"SSTM-{new_pid}.dat",
            f"MU-{old_pid}.dat": f"MU-{new_pid}.dat",
            f"OS-{old_pid}.dat": f"OS-{new_pid}.dat",
            f"SS-{old_pid}.dat": f"SS-{new_pid}.dat",
            f"audio_{lang}{country}{lab_no}_{old_pid:03d}": f"audio_{lang}{country}{lab_no}_{new_pid:03d}",
        }

        for root, dirs, files in os.walk(subfolder):
            # Change directory names
            for i, d in enumerate(dirs):
                for filestart, new_filestart in filename_mappings.items():
                    if d.startswith(filestart):
                        new_dirname = d.replace(filestart, new_filestart)
                        print(f"Renaming {d} to {new_dirname}")
                        old_path = Path(root) / d
                        new_path = Path(root) / new_dirname
                        os.rename(old_path, new_path)
                        dirs[i] = new_dirname

            for f in files:
                # Change pid in csvs
                if f.endswith(".csv"):
                    print(f"Editing pid in csv {f}")
                    f_path = Path(root) / f
                    _change_pid_in_csv(f_path, new_pid)

                # Change filename if applicable
                for filestart, new_filestart in filename_mappings.items():
                    if f.startswith(filestart):
                        new_filename = f.replace(filestart, new_filestart)
                        print(f"Renaming {f} to {new_filename}")
                        old_path = Path(root) / f
                        new_path = Path(root) / new_filename
                        os.rename(old_path, new_path)

        # Changing the session folder name
        new_path = psych_path / (f"{new_pid:03d}" + session_id[3:])
        os.rename(subfolder, new_path)


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
