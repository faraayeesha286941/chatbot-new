
# jadiiiiiiii
# import pandas as pd

# # === File paths ===
# oss_path = r"C:\Users\noora\Desktop\CD WEB GIS PLATFORM\DATAS\OSS_data.csv"
# site_info_path = r"C:\Users\noora\Desktop\CD WEB GIS PLATFORM\DATAS\site_info_4g.csv"
# output_path = r"C:\Users\noora\Desktop\CD WEB GIS PLATFORM\DATAS\OSS_data_with_cellname.csv"

# # === Load CSVs ===
# oss_df = pd.read_csv(oss_path, dtype={'enodebid': str, 'cellid': str})
# site_df = pd.read_csv(site_info_path, dtype={'enodeb_id': str, 'cell_id': str})

# # === Prepare key columns ===
# site_df['enodebid'] = site_df['enodeb_id'].astype(str).str.strip()
# site_df['cellid'] = site_df['cell_id'].astype(str).str.strip()
# site_df['cell_name'] = site_df['cell_name'].astype(str).str.strip()

# oss_df['enodebid'] = oss_df['enodebid'].astype(str).str.strip()
# oss_df['cellid'] = oss_df['cellid'].astype(str).str.replace('.0', '', regex=False).str.strip()

# # === Merge OSS data with site info to get cell_name ===
# merged_df = pd.merge(
#     oss_df,
#     site_df[['enodebid', 'cellid', 'cell_name']],
#     how='left',
#     on=['enodebid', 'cellid']
# )

# # === Export merged CSV ===
# merged_df.to_csv(output_path, index=False)
# print(f"✅ OSS data now includes cell_name. Exported to:\n{output_path}")




# import pandas as pd

# # === File paths ===
# oss_path = r"C:\Users\noora\Desktop\CD WEB GIS PLATFORM\DATAS\OSS_data.csv"
# site_info_path = r"C:\Users\noora\Desktop\CD WEB GIS PLATFORM\DATAS\site_info_4g.csv"
# kepong_path = r"C:\Users\noora\Desktop\GITHUB CD\30_Site_Kepong2.csv"  # <== this has height
# output_path = r"C:\Users\noora\Desktop\CD WEB GIS PLATFORM\DATAS\wedges.csv"

# # === Load CSVs ===
# oss_df = pd.read_csv(oss_path, dtype={'enodebid': str, 'cellid': str})
# site_df = pd.read_csv(site_info_path, dtype={'enodeb_id': str, 'cell_id': str})
# kepong_df = pd.read_csv(kepong_path)

# # === Prepare key columns ===
# site_df['enodebid'] = site_df['enodeb_id'].astype(str).str.strip()
# site_df['cellid'] = site_df['cell_id'].astype(str).str.strip()
# site_df['cell_name'] = site_df['cell_name'].astype(str).str.strip()

# oss_df['enodebid'] = oss_df['enodebid'].astype(str).str.strip()
# oss_df['cellid'] = oss_df['cellid'].astype(str).str.replace('.0', '', regex=False).str.strip()

# # === Merge OSS with site_info_4g to get cell_name ===
# merged_df = pd.merge(
#     oss_df,
#     site_df[['enodebid', 'cellid', 'cell_name']],
#     how='left',
#     on=['enodebid', 'cellid']
# )

# # === Merge with 30_Site_Kepong2 to get height ===
# kepong_df['cell_name'] = kepong_df['cell_name'].astype(str).str.strip()
# merged_df = pd.merge(
#     merged_df,
#     kepong_df[['cell_name', 'height', 'longitude', 'latitude', 'azimuth', 'vendor', 'region', 'site_type', 'band', 'list', 'beam', 'radius'
# ]],
#     how='left',
#     on='cell_name'
# )

# # === Export final CSV ===
# merged_df.to_csv(output_path, index=False)
# print(f"✅ Final OSS data now includes cell_name and height. Exported to:\n{output_path}")
