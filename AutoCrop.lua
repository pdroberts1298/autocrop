-- LR imports
local LrApplication = import("LrApplication")
local LrApplicationView = import("LrApplicationView")
local LrBinding = import("LrBinding")
local LrDevelopController = import("LrDevelopController")
local LrDialogs = import("LrDialogs")
local LrExportSession = import("LrExportSession")
local LrFileUtils = import("LrFileUtils")
local LrFunctionContext = import("LrFunctionContext")
local LrLogger = import("LrLogger")
local LrPathUtils = import("LrPathUtils")
local LrProgressScope = import("LrProgressScope")
local LrTasks = import("LrTasks")

local log = LrLogger("AutoCrop")
log:enable("logfile")

-- Global settings
local detectProgram = LrPathUtils.child(_PLUGIN.path, "detect.py")

-- Create directory to save temporary exports to
local imgPreviewPath = LrPathUtils.child(_PLUGIN.path, "render")

if LrFileUtils.exists(imgPreviewPath) ~= true then
  LrFileUtils.createDirectory(imgPreviewPath)
end

local catalog = LrApplication.activeCatalog()

function setCrop(photo, angle, cropLeft, cropRight, cropTop, cropBottom)
  if LrApplicationView.getCurrentModuleName() == "develop" and photo == catalog:getTargetPhoto() then
    LrDevelopController.setValue("CropConstrainAspectRatio", false)
    LrDevelopController.setValue("straightenAngle", angle)
    LrDevelopController.setValue("CropLeft", cropLeft)
    LrDevelopController.setValue("CropRight", cropRight)
    LrDevelopController.setValue("CropTop", cropTop)
    LrDevelopController.setValue("CropBottom", cropBottom)
  else
    local settings = {}
    settings.CropConstrainAspectRatio = false
    settings.CropLeft = cropLeft
    settings.CropRight = cropRight
    settings.CropTop = cropTop
    settings.CropBottom = cropBottom
    settings.CropAngle = -angle
    photo:applyDevelopSettings(settings)
  end
end

-- Convert a Windows absolute path to a Linux Sub-Sytem path
function lssPath(winPath)
  -- Replace Windows drive with mount point in Linux subsystem
  local path = winPath:gsub("^(.+):", function(c)
  return "/mnt/" .. c:lower()
  end)

  -- Flip slashes the right way
  return path:gsub("%\\", "/")
end

-- Given a string delimited by whitespace, split into numbers
function splitLinesToNumbers(data)
  result = {}

  for val in string.gmatch(data, "%S+") do
    result[#result+1] = tonumber(val)
  end

  return result
end

function rotateCropForOrientation(crop, orientation)

  if orientation == "AB" then
    -- No adjustments needed: this is the orientation of the data
    return rawCrop

  elseif orientation == "BC" then
    return {
      right = crop.bottom,
      bottom = 1 - crop.left,
      left = crop.top,
      top = 1 - crop.right,
      angle = crop.angle,
    }

  elseif orientation == "CD" then
    return {
      bottom = 1 - crop.top,
      left = 1 - crop.right,
      top = 1 - crop.bottom,
      right = 1 - crop.left,
      angle = crop.angle,
    }

  elseif orientation == "DA" then
    return {
      left = 1 - crop.bottom,
      top = crop.left,
      right = 1 - crop.top,
      bottom = crop.right,
      angle = crop.angle,
    }
  end
end

function processPhotos(photos)
  LrFunctionContext.callWithContext("export", function(exportContext)

    local progressScope = LrDialogs.showModalProgressDialog({
      title = "Auto negative crop",
      caption = "Analysing image with OpenCV",
      cannotCancel = false,
      functionContext = exportContext
    })

    local exportSession = LrExportSession({
      photosToExport = photos,
      exportSettings = {
        LR_collisionHandling = "rename",
        LR_export_bitDepth = "8",
        LR_export_colorSpace = "sRGB",
        LR_export_destinationPathPrefix = imgPreviewPath,
        LR_export_destinationType = "specificFolder",
        LR_export_useSubfolder = false,
        LR_format = "JPEG",
        LR_jpeg_quality = 1,
        LR_minimizeEmbeddedMetadata = true,
        LR_outputSharpeningOn = false,
        LR_reimportExportedPhoto = false,
        LR_renamingTokensOn = true,
        LR_size_doConstrain = true,
        LR_size_doNotEnlarge = true,
        LR_size_maxHeight = 1500,
        LR_size_maxWidth = 1500,
        LR_size_units = "pixels",
        LR_tokens = "{{image_name}}",
        LR_useWatermark = false,
      }
    })

    local numPhotos = exportSession:countRenditions()

    local renditionParams = {
      progressScope = progressScope,
      renderProgressPortion = 1,
      stopIfCanceled = true,
    }

    for i, rendition in exportSession:renditions(renditionParams) do

      -- Stop processing if the cancel button has been pressed
      if progressScope:isCanceled() then
        break
      end

      -- Common caption for progress bar
      local progressCaption = rendition.photo:getFormattedMetadata("fileName") .. " (" .. i .. "/" .. numPhotos .. ")"

      progressScope:setPortionComplete(i - 1, numPhotos)
      progressScope:setCaption("Processing " .. progressCaption)

      rendition:waitForRender()

      local photoPath = rendition.destinationPath
      local dataPath = photoPath .. ".txt"

      local cmd = "bash -c 'DISPLAY=:0 python \"" .. lssPath(detectProgram) .. "\" \"" .. lssPath(photoPath) .. "\"'"
      log:trace("Executing: " .. cmd)

      exitCode = LrTasks.execute(cmd)

      if exitCode ~= 0 then
        LrDialogs.showError("Detect program returned a non-zero status: " .. exitCode )
        break
      end

      if LrFileUtils.exists(dataPath) == false then
        LrDialogs.showError("Detect program exited cleanly, but the output data file was not found:\n\n" .. dataPath)
        break
      end

      -- Read crop points from analysis output
      -- The directions/sides here are relative to the image that was processed
      rawData = LrFileUtils.readFile(dataPath)
      cropData = splitLinesToNumbers(rawData)

      rawCrop = {
        left = cropData[1],
        right  = cropData[2],
        top  = cropData[3],
        bottom  = cropData[4],
        angle = cropData[5],
      }

      -- Re-orient cropping data to "AB" so the crop is applied as intended
      -- (Crop is always relative to the "AB" orientation in Lightroom)
      developSettings = rendition.photo:getDevelopSettings()
      crop = rotateCropForOrientation(rawCrop, developSettings["orientation"])

      LrTasks.startAsyncTask(function()
        catalog:withWriteAccessDo("Apply crop", function(context)
          setCrop(
            rendition.photo,
            crop.angle,
            crop.left,
            crop.right,
            crop.top,
            crop.bottom
          )
        end, {
          timeout = 2
        })
      end)

      LrFileUtils.delete(photoPath)
      LrFileUtils.delete(dataPath)
    end
  end)
end

-- Collect photos to operate on
local targetPhotos = {}

if LrApplicationView.getCurrentModuleName() == "develop" then
  targetPhotos[1] = catalog.targetPhoto
elseif LrApplicationView.getCurrentModuleName() == "library" then
  targetPhotos = catalog.targetPhotos
end

-- Run autocrop
LrTasks.startAsyncTask(function()

  -- Reset all crops so the exports can be processed properly
  LrDevelopController.resetCrop()

  -- Process crops externally and apply
  processPhotos(targetPhotos)
end)

return {}