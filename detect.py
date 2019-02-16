import cv2
import copy
import math
import numpy as np
import os

MAX_COVERAGE = 0.95
INSET_PERCENT = 0.005

def getRect(img, ignoreMask, lowerThresh, upperThresh):

    # Threshold the gray image to binarize, and negate it
    # _, binary = cv2.threshold(img, lowerThresh, upperThresh, cv2.THRESH_BINARY) # THRESH_TOZERO_INV
    # binary = cv2.bitwise_not(binary)

    _, binary = cv2.threshold(img, lowerThresh, upperThresh, cv2.THRESH_BINARY_INV) # THRESH_TOZERO_INV
    # binary = cv2.bitwise_not(binary)

    binary = cv2.bitwise_and(ignoreMask, binary)

    # Prevent tiny outlier collections of pixels spoiling the rect fitting
    kernel = np.ones((5,5),np.uint8)
    binary = cv2.erode(binary, kernel, iterations = 3)

    thresholdImg = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    largestRect = None
    largestArea = 0

    # Find external contours of all shapes
    contours,_ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # _, contours, hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        area = cv2.contourArea(cnt)

        # Keep track of the largest area seen
        if area > largestArea:
            largestArea = area
            largestRect = cv2.minAreaRect(cnt)

    return largestRect, largestArea, thresholdImg

def medianRect(rects):
    return (
        (np.median([r[0][0] for r in rects]), np.median([r[0][1] for r in rects])),
        (np.median([r[1][0] for r in rects]), np.median([r[1][1] for r in rects])),
        np.median([r[2] for r in rects])
    )

def correctAspectRatio(rect, targetRatio = 1.5, maxDifference = 0.3):
    """
    Return an aspect-ratio corrected rect (and success flag)

    Args:
        rect (OpenCV RotatedRect struct)
        targetRatio (float): Ratio represented as the larger image dimension divided by the smaller one

    """
    # Indexes into the rect nested tuple
    CENTER = 0; SIZE = 1; ANGLE = 2
    X = 0; Y = 1;

    size = rect[SIZE]

    aspectRatio = max(size[X], size[Y]) / float(min(size[X], size[Y]))
    aspectError = targetRatio - aspectRatio

    # Factor out orientation to simplify logic below
    # This assumes the larger dimension as X
    if size[X] == max(size[X], size[Y]):
        rectWidth = size[X]
        rectHeight = size[Y]
        widthDim = X
        heightDim = Y
    else:
        rectHeight = size[X]
        rectWidth = size[Y]
        widthDim = Y
        heightDim = X

    # Only attempt to correct aspect ratio where the ROI is roughly right already
    # This prevents odd results for poor outline detection
    if abs(aspectError) > maxDifference:
        return rect, False

    # Shrink width if the ratio was too wide
    if aspectRatio > targetRatio:
        rectWidth = size[heightDim] * targetRatio

    # Shrink height if the ratio was too tall
    elif aspectRatio < targetRatio:
        rectHeight = size[widthDim] / targetRatio

    # Apply new width/height in the original orientation
    if widthDim == X:
        newSize = (rectWidth, rectHeight)
    else:
        newSize = (rectHeight, rectWidth)

    newRect = (rect[CENTER], newSize, rect[ANGLE])

    return newRect, True

def findExposureBounds(img, showOutputWindow=False):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Smooth out noise
    # gray = cv2.GaussianBlur(gray,(5,5),0)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)

    # Maximise brightness range
    gray = cv2.equalizeHist(gray)


    # Create a mask to ignore the brightest spots
    # These are usually where there is no film covering the light source
    _, ignoreMask = cv2.threshold(gray, 240, 0, cv2.THRESH_TOZERO)
    ignoreMask = cv2.bitwise_not(ignoreMask)

    # Expand masked out area slightly to include adjacent edges
    kernel = np.ones((3,3),np.uint8)
    ignoreMask = cv2.erode(ignoreMask, kernel, iterations = 3)


    # Get min/max region of interest areas
    height, width, _  = img.shape
    maxArea = (height * MAX_COVERAGE)  * (width * MAX_COVERAGE)

    lowerThreshold = 0
    upperThreshold = 220
    box = None

    results = []

    while upperThreshold > lowerThreshold:
        rect, area, debugImg = getRect(gray, ignoreMask, lowerThreshold, upperThreshold)

        # Stop once a valid result is returned
        if area >= maxArea:
            break

        if area >= maxArea * 0.55:
            results.append(rect)
            lowerThreshold += 1

            # Draw in green for results that are collected
            debugLineColour = (0, 255, 0)

        else:
            lowerThreshold += 5

            # Draw in red for areas that were too small
            debugLineColour = (0, 0, 255)


        if showOutputWindow:
            if rect is not None:
                # Get a rectangle around the contour

                rectPoints = cv2.cv.BoxPoints(rect)
                # rectPoints = cv2.boxPoints(largestRect)
                rectPoints = np.int0(rectPoints)

                cv2.drawContours(debugImg, [rectPoints], -1, debugLineColour, 3)

            # Draw threshold on debug output
            cv2.putText(
                img=debugImg,
                text='Threshold: ' + str(lowerThreshold),
                org=(20, 30),
                fontFace=cv2.FONT_HERSHEY_PLAIN,
                fontScale=2,
                color=(0, 150, 255),
                lineType=4
            )

            cv2.imshow('image', cv2.resize(debugImg, (0,0), fx=0.75, fy=0.75) )
            cv2.waitKey(1)

    return medianRect(results)


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description='Find crop for film negative scan')

    parser.add_argument('files', nargs='+', help='Image files to perform detection on (JPG, PNG, etc)')

    args = parser.parse_args()

    hasDisplay = os.getenv('DISPLAY') != None

    for filename in args.files:
        # read image and convert to gray
        img = cv2.imread(filename, cv2.IMREAD_UNCHANGED)

        rawRect = findExposureBounds(img, showOutputWindow=hasDisplay)

        # Outputs for Lightroom
        cropLeft = 0
        cropRight = 1.0
        cropTop = 0
        cropBottom = 1.0
        rotation = 0

        if rawRect is not None:
            # Average height and width of the detected area to get a constant inset
            insetPixels = ((rawRect[1][0] + rawRect[1][1]) / 2.0) * INSET_PERCENT

            insetRect = (
                rawRect[0], # Center
                (rawRect[1][0] - insetPixels, rawRect[1][1] - insetPixels), # Size
                rawRect[2] # Rotation
            )

            rect, aspectChanged = correctAspectRatio(insetRect)

            boxWidth = rect[1][0]
            boxHeight = rect[1][1]

             # box = cv2.boxPoints(rect)
            box = np.int0(cv2.cv.BoxPoints(rect))

            # Caclulate white balance from average colour outside of frame?
            # # Create a mask that excludes areas that are probably the directly visible light source
            # _, wbMask = cv2.threshold(gray, 253, 0, cv2.THRESH_TOZERO)
            # wbMask = cv2.bitwise_not(wbMask)

            # # Mask out the detected frame - we only want to look at the base film layer
            # cv2.fillConvexPoly(wbMask, box, 0)

            # # cv2.imshow('image', wbMask )
            # # cv2.waitKey(0)

            # # bgr = cv2.mean(img, wbMask)
            # lab = cv2.mean(cv2.cvtColor(img, cv2.COLOR_BGR2LAB), wbMask)

            # # print [i for i in reversed(bgr)]
            # tint = lab[1] - 127
            # temperature = lab[2] - 127
            # print (lab[0]/255.0)*100, temperature, tint


            # Lightroom doesn't support rotation more than 45 degrees
            # The detected rect usually includes a 90 degree rotation for landscape images
            rotation = -rect[2]

            if rotation > 45:
                rotation -= 90
            elif rotation < -90:
                rotation += 45

            # Calculate crops in a format for Lightroom (0.0 to 1.0 for each edge)
            centerX = rect[0][0]
            centerY = rect[0][1]

            # Use the average distance from each side as the crop in Lightroom
            imgHeight, imgWidth, _  = img.shape

            top = []; left = []; right = []; bottom =[]

            for point in box:
                # point = rotateAroundPoint(point, math.radians(rotation))

                if point[0] > centerX:
                    right.append( point[0] )
                else:
                    left.append( point[0] )

                if point[1] > centerY:
                    bottom.append( point[1] )
                else:
                    top.append( point[1] )

            cropRight = (min(right)) / float(imgWidth)
            cropLeft = (max(left)) / float(imgWidth)
            cropBottom = (min(bottom)) / float(imgHeight)
            cropTop = (max(top)) / float(imgHeight)

            # Draw original detected area
            rawBox = np.int0(cv2.cv.BoxPoints(rawRect))
            cv2.drawContours(img, [rawBox], -1, (255, 0, 0), 1)

            # Draw inset area
            insetBox = np.int0(cv2.cv.BoxPoints(insetRect))
            cv2.drawContours(img, [insetBox], -1, (0, 255, 255), 1)

            # Draw adjusted aspect ratio area
            cv2.drawContours(img, [box], -1, (0, 255, 0), 2)

            cv2.circle(img, (int(rect[0][0]), int(rect[0][1])), 3, (0, 255, 0), 3)

        # Write result to disk for Lightroom plugin to pick up
        # (The Lightroom API doesn't appear to allow streaming in output from a program)
        cropData = [
            cropLeft,
            cropRight,
            cropTop,
            cropBottom,
            rotation
        ]

        with file(filename + ".txt", 'w') as out:
            out.write("\r\n".join(str(x) for x in cropData))

        cv2.imwrite(filename + "-analysis.jpg", img)

        if hasDisplay:
            cv2.imshow('image', cv2.resize(img, (0,0), fx=0.75, fy=0.75) )
            cv2.waitKey(1000)
