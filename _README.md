# Film negative auto-crop plugin for Lightroom 6

This is a proof of concept plugin for Adobe Lightroom 6 that automatically crops
scanned film negatives to only the exposed area of the emulsion using OpenCV.

The detection works, but it could be better. Currently it does a single pass:

1. Mask out extremely bright points (eg. light coming through the sprocket holes)
2. Threshold the image starting from zero, increasing in steps
3. At each threshold, collect the rotated bounding rectangle around the largest contour/blob (larger than a minimum size)
4. Once the largest contour/blob is too large, stop collecting rects
5. Calculate the crop for the image using the median of the collected rectangles

This works most of the time, but fails on images that threshold to many smaller contours that don't join (eg. one in each corner).

## Setup (rough)

- Lightroom on Windows (OSX should work too with some tweaks)
- OpenCV 2.x and Python installed in the Windows 10 Linux Subsystem, because Python+OpenCV on Windows is a pain to set up
- Xming (X server for Windows) running to allow windows from the Python script