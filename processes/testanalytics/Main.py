import rasterio
from skimage import filters, measure, morphology, segmentation
import numpy as np

import geopandas as gpd
from shapely.geometry import shape
import rasterio.features

import matplotlib.pyplot as plt
import rasterio
from rasterio.plot import show

# Open the Sentinel-2 image
with rasterio.open('E:\imagery\PHR1A_acq20210906_del77dd7096\IMG_PHR1A_PMS_001\IMG_PHR1A_PMS_202109060618006_ORT_c6fb0de8-7ddf-470b-c770-6e185ba87a03-001_R1C1.TIF') as ds:
    img = ds.read([1, 2, 3])  # Read the RGB bands

# Calculate a threshold value using Otsu's method
threshold = filters.threshold_otsu(img)

# Apply the threshold to create a binary image
binary_img = img > threshold

# Perform morphological operations to remove small objects and to fill holes
clean_img = morphology.remove_small_objects(binary_img, min_size=1000)  # Adjust min_size as needed
clean_img = morphology.remove_small_holes(clean_img, area_threshold=500)  # Adjust area_threshold as needed

# Label the different objects in the image
label_img = measure.label(clean_img)

# Count the number of different objects
n_trees = label_img.max()

print(f'Number of trees: {n_trees}')

# Get the shapes as (geometry, value) tuples
shapes = list(rasterio.features.shapes(label_img.astype(np.int16), transform=ds.transform))

# Convert the shapes into a GeoDataFrame
gdf = gpd.GeoDataFrame([{'geometry': shape(geom), 'label': label} for geom, label in shapes if label > 0])

# Set the CRS of the GeoDataFrame to match the original image
gdf.crs = ds.crs

# Write the GeoDataFrame to a shapefile
gdf.to_file('trees.shp')

# # Open the shapefile
# gdf = gpd.read_file('trees.shp')

# Create a subplot
fig, ax = plt.subplots(1, figsize=(12, 12))

# Display the TIFF file
show(img, ax=ax)

# Display the shapefile. Adjust the color and edge color as needed.
gdf.boundary.plot(ax=ax, color=None, edgecolor='r', linewidth=2)

# Display the plot
plt.show()
