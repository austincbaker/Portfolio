package com.android.while_youre_out

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent


class BroadcastReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        GeofenceTransitionIntentHandler.enqueueWork(context, intent)
    }
}