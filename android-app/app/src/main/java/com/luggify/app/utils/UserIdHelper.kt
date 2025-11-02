package com.luggify.app.utils

import android.content.Context
import android.provider.Settings

object UserIdHelper {
    fun getUserId(context: Context): String {
        return Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ANDROID_ID
        ) ?: "android_user_${System.currentTimeMillis()}"
    }
}

