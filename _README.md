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

[Images of this running can be seen on the Hackaday.io](https://hackaday.io/project/162842-35mm-flim-negative-scanning/log/159448-auto-cropping-scanned-negatives-with-opencv)

## Setup (rough)

- Lightroom on Windows (OSX should work too with some tweaks)
- OpenCV 2.x and Python installed in the Windows 10 Linux Subsystem, because Python+OpenCV on Windows is a pain to set up
- Xming (X server for Windows) running to allow windows from the Python script

## Notes on the Lightroom Lua API

Lightroom's API is very poorly documented (unless I'm missing some newer docs that Adobe has locked away behind a login). It doesn't appear to be intended for anything other than exporting to custom APIs - seems strange considering how extensible Photoshop is with scripts and plugins.

Images can be cropped through the Lightroom Lua API using the parameters `CropLeft`, `CropRight`, `CropTop`, and `CropBottom`. These aren't listed on the `LrDevelopController` page of the SDK docs, but are listed in the docs under `LrPhoto:getDevelopSettings`. Note that the sides (top, right, etc) are *always* relative to the orientation `AB`, not necessarily the top, right, etc of the exported image.

The `orientation` param is a two character string that represents the two corners at the top of the image:

```
AB:         BC:       CD:         DA:

A-----B     B---C     C-----D     D---A
|     |     |   |     |     |     |   |
D-----C     |   |     B-----A     |   |
            A---B                 C---B

(Each of these is rotated anti-clockwise by 90 degrees)
```

In my testing, `orientation` couldn't be read using `LrDevelopController:getValue()`, but I could retrieve it using `LrPhoto:photo:getDevelopSettings`.