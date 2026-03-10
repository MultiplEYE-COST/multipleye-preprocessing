import pandas as pd


def remap_space_to_following_word(aoi_file_path):
    aoi_df = pd.read_csv(aoi_file_path)

    # Identify rows where the 'word' column is empty and the char is a space
    # then increase the word index of just the space by 1 to match the following word
    # then write the modified dataframe back to the same file
    for i in range(len(aoi_df) - 1):
        if aoi_df.loc[i, "word"] == "" and aoi_df.loc[i, "char"] == " ":
            aoi_df.loc[i, "word"] = aoi_df.loc[i + 1, "word"]

    aoi_df.to_csv(aoi_file_path, index=False)
