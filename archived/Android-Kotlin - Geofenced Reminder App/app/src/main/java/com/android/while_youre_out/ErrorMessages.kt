package com.android.while_youre_out


import android.content.Context
import com.google.android.gms.common.api.ApiException
import com.google.android.gms.location.GeofenceStatusCodes

object ErrorMessages {
    fun getErrorString(context: Context, e: Exception): String {
        return if (e is ApiException) {
            getErrorString(context, e.statusCode)
        } else {
            context.resources.getString(R.string.unknown_error)
        }
    }

    fun getErrorString(context: Context, errorCode: Int): String {
        val resources = context.resources
        return when (errorCode) {
            GeofenceStatusCodes.GEOFENCE_NOT_AVAILABLE ->
                resources.getString(R.string.geofence_unavailable)

            GeofenceStatusCodes.GEOFENCE_TOO_MANY_GEOFENCES ->
                resources.getString(R.string.too_many_geofences)

            GeofenceStatusCodes.GEOFENCE_TOO_MANY_PENDING_INTENTS ->
                resources.getString(R.string.geofence_too_many_pending_intents)

            else -> resources.getString(R.string.unknown_error)
        }
    }
}