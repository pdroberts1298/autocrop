return {

    LrSdkVersion = 6.0,
    LrSdkMinimumVersion = 6.0,
    LrToolkitIdentifier = 'nz.co.stecman.negativeautocrop',

    LrPluginName = "Negative Auto Crop",

    LrExportMenuItems = {
        {
            title = "Auto &Crop Negative",
            file = "AutoCrop.lua",
            enabledWhen = "photosSelected"
        }
    },

    VERSION = {
        major=1,
        minor=0,
        revision=0,
    }
}