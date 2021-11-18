package com.android.while_youre_out

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.SeekBar
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationServices
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.GoogleMap
import com.google.android.gms.maps.OnMapReadyCallback
import com.google.android.gms.maps.SupportMapFragment
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.android.material.snackbar.Snackbar
import kotlinx.android.synthetic.main.activity_new_reminder.*


class CreateNewReminder : Base(), OnMapReadyCallback {


    private lateinit var map: GoogleMap
    private var reminder = Reminder(latLng = null, radius = null, description = "null")


    private val permissionRequestFineALocation = 1
    var locationPermissionGranted = false
    private var lastKnownLocation: Location? = null
    private lateinit var latLng: LatLng
    private lateinit var cameraPosition: CameraPosition
    private lateinit var fusedLocationProviderClient: FusedLocationProviderClient


    // A default location (Google HQ) and default zoom to use when location permission is
    // not granted.
    private val defaultLocation = LatLng(37.4221, 122.0841)



    private val radiusBarChangeListener = object : SeekBar.OnSeekBarChangeListener {
        override fun onStartTrackingTouch(seekBar: SeekBar?) {}

        override fun onStopTrackingTouch(seekBar: SeekBar?) {}

        override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
            updateRadiusWithProgress(progress)

            showReminderUpdate()
        }
    }

    private fun updateRadiusWithProgress(progress: Int) {
        val radius = getRadius(progress)
        reminder.radius = radius
    }


    companion object {
        private const val extraLatLng = "extraLatLng"
        private const val extraZoom = "extraZoom"

        private const val defaultZoom = 15f
        const val keyLocation = "location"
        private val TAG = CreateNewReminder::class.java.simpleName

        fun utilityIntent(context: Context, latLng: LatLng, zoom: Float): Intent {
            val utilityIntent = Intent(context, WhileYoureOut::class.java)
            utilityIntent
                .putExtra(extraLatLng, latLng)
                .putExtra(extraZoom, zoom)
            return utilityIntent
        }
    }



    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_new_reminder)

        if (savedInstanceState != null) {
            lastKnownLocation = savedInstanceState.getParcelable(keyLocation)
        }
        // Construct a FusedLocationProviderClient.
        fusedLocationProviderClient = LocationServices.getFusedLocationProviderClient(this)

        val mapFragment = supportFragmentManager
            .findFragmentById(R.id.map) as SupportMapFragment
        mapFragment.getMapAsync(this)

        Instructions.visibility = View.GONE
        instructionsDescribed.visibility = View.GONE
        setRadius.visibility = View.GONE
        reminderName.visibility = View.GONE

        supportActionBar?.setDisplayHomeAsUpEnabled(true)
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    override fun onMapReady(googleMap: GoogleMap) {
        map = googleMap
        map.uiSettings.isMapToolbarEnabled = true
        latLng = LatLng(intent.getStringExtra("lat").toString().toDouble(),intent.getStringExtra("lon").toString().toDouble() )
        cameraPosition = CameraPosition.builder().target(latLng)
            .zoom(15f).bearing(0f).tilt(45f).build()
        map.moveCamera(CameraUpdateFactory
            .newLatLngZoom(cameraPosition.target, intent.getStringExtra("mainZoom").toString().toFloat()))

        showConfigureLocationStep()
    }

    private fun showConfigureLocationStep() {
        pin.visibility = View.VISIBLE
        Instructions.visibility = View.VISIBLE
        instructionsDescribed.visibility = View.VISIBLE
        setRadius.visibility = View.GONE
        reminderName.visibility = View.GONE
        Instructions.text = getString(R.string.drop_the_pin)
        finish.setOnClickListener {
            reminder.latLng = map.cameraPosition.target
            showConfigureRadiusStep()
        }

        showReminderUpdate()
    }

    private fun showConfigureRadiusStep() {
        pin.visibility = View.GONE
        Instructions.visibility = View.VISIBLE
        instructionsDescribed.visibility = View.GONE
        setRadius.visibility = View.VISIBLE
        reminderName.visibility = View.GONE
        Instructions.text = getString(R.string.set_radius_size)
        finish.setOnClickListener {
            showConfigureMessageStep()
        }
        setRadius.setOnSeekBarChangeListener(radiusBarChangeListener)
        updateRadiusWithProgress(setRadius.progress)

        map.animateCamera(CameraUpdateFactory.zoomTo(15f))

        showReminderUpdate()
    }

    private fun getRadius(progress: Int) = progress.toDouble()/2

    private fun showConfigureMessageStep() {
        pin.visibility = View.GONE
        Instructions.visibility = View.VISIBLE
        instructionsDescribed.visibility = View.GONE
        setRadius.visibility = View.GONE
        reminderName.visibility = View.VISIBLE
        Instructions.text = getString(R.string.set_reminder_name)
        finish.setOnClickListener {
            hideKeyboard(this, reminderName)
            val describe = reminderName.text.toString()
            if(describe != "null") {
                print(reminderName.text.toString())
                reminder.description = describe.toString()
                if (reminder.description.isNullOrEmpty()) {
                    reminderName.error = getString(R.string.error_required)
                } else {
                    addReminder(reminder)
                }
            }
        }
        reminderName.requestFocusWithKeyboard()

        showReminderUpdate()
    }

    private fun addReminder(reminder: Reminder) {
        getRepository().add(reminder,
            success = {
                setResult(RESULT_OK)
                finish()
            },
            failure = {
                Snackbar.make(main, it, Snackbar.LENGTH_LONG).show()
            })
    }

    private fun showReminderUpdate() {
        map.clear()
        showReminderInMap(this, map, reminder)
    }


/*
    private fun getDeviceLocation() {
        *//*
         * Get the best and most recent location of the device, which may be null in rare
         * cases when a location is not available.
         *//*
        try {
            if (locationPermissionGranted) {
                val locationResult = fusedLocationProviderClient.lastLocation
                locationResult.addOnCompleteListener(this) { task ->
                    if (task.isSuccessful) {
                        // Set the map's camera position to the current location of the device.
                        lastKnownLocation = task.result
                        if (lastKnownLocation != null) {
                            map.moveCamera(CameraUpdateFactory.newLatLngZoom(
                                LatLng(lastKnownLocation!!.latitude,
                                    lastKnownLocation!!.longitude), defaultZoom.toFloat()))
                        }
                    } else {
                        Log.d(CreateNewReminder.TAG, "Current location is null. Using defaults.")
                        Log.e(TAG, "Exception: %s", task.exception)
                        map.moveCamera(CameraUpdateFactory
                            .newLatLngZoom(defaultLocation, defaultZoom.toFloat()))
                        map.uiSettings?.isMyLocationButtonEnabled = false
                    }
                }
            }
        } catch (e: SecurityException) {
            Log.e("Exception: %s", e.message, e)
        }
    }

    private fun getLocationPermission() {
        *//*
         * Request location permission, so that we can get the location of the
         * device. The result of the permission request is handled by a callback,
         * onRequestPermissionsResult.
         *//*
        if (ContextCompat.checkSelfPermission(this.applicationContext,
                Manifest.permission.ACCESS_FINE_LOCATION)
            == PackageManager.PERMISSION_GRANTED) {
            locationPermissionGranted = true
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.ACCESS_FINE_LOCATION),
                permissionRequestFineALocation
            )
        }
    }



    *//*
     * Updates the map's UI settings based on whether the user has granted location permission.
     *//*
    // [START maps_current_place_update_location_ui]
    private fun updateLocationUI() {
        try {
            if (locationPermissionGranted) {
                map.isMyLocationEnabled = true
                map.uiSettings?.isMyLocationButtonEnabled = true
            } else {
                map.isMyLocationEnabled = false
                map.uiSettings?.isMyLocationButtonEnabled = false
                lastKnownLocation = null
                getLocationPermission()
            }
        } catch (e: SecurityException) {
            Log.e("Exception: %s", e.message, e)
        }
    }*/

}