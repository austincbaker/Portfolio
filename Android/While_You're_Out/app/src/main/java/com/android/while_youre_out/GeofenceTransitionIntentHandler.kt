package com.android.while_youre_out

import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.app.JobIntentService
import com.google.android.gms.location.Geofence
import com.google.android.gms.location.GeofencingEvent


class GeofenceTransitionIntentHandler : JobIntentService() {

    companion object {
        private const val LOG_TAG = "GeoTrIntentService"

        private const val JOB_ID = 1991

        fun enqueueWork(context: Context, intent: Intent) {
            enqueueWork(
                context,
                GeofenceTransitionIntentHandler::class.java, JOB_ID,
                intent)
        }
    }

    override fun onHandleWork(intent: Intent) {
        val geofencingEvent = GeofencingEvent.fromIntent(intent)
        if (geofencingEvent.hasError()) {
            val errorMessage = ErrorMessages.getErrorString(this,
                geofencingEvent.errorCode)
            Log.e(LOG_TAG, errorMessage)
            return
        }

        handleEvent(geofencingEvent)
    }

    private fun handleEvent(event: GeofencingEvent) {
        if (event.geofenceTransition == Geofence.GEOFENCE_TRANSITION_ENTER) {
            val reminder = getFirstReminder(event.triggeringGeofences)
            val message = reminder?.description
            val latLng = reminder?.latLng
            if (message != null && latLng != null) {
                sendNotification(this, message, latLng)
            }
        }
    }

    private fun getFirstReminder(triggeringGeofences: List<Geofence>): Reminder? {
        val firstGeofence = triggeringGeofences[0]
        return (application as ReminderApp).getRepository().get(firstGeofence.requestId)
    }
}
