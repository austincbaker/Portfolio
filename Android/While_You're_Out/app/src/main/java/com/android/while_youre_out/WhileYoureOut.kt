package com.android.while_youre_out

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.View
import androidx.annotation.RequiresApi
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.android.while_youre_out.*
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationServices
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.GoogleMap
import com.google.android.gms.maps.OnMapReadyCallback
import com.google.android.gms.maps.SupportMapFragment
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.Marker
import com.google.android.material.floatingactionbutton.FloatingActionButton
import com.google.android.material.snackbar.Snackbar
import kotlinx.android.synthetic.main.activity_main.*

class WhileYoureOut : Base(), OnMapReadyCallback, GoogleMap.OnMarkerClickListener,GoogleMap.OnCameraIdleListener {

    //
        private val PERMISSIONS_REQUEST_ACCESS_FINE_LOCATION = 1
        var locationPermissionGranted = false
        private var lastKnownLocation: Location? = null
        private lateinit var fusedLocationProviderClient: FusedLocationProviderClient


        // A default location (Google HQ) and default zoom to use when location permission is
        // not granted.
        private val defaultLocation = LatLng(37.4221, 122.0841)

    private var map: GoogleMap? = null

    companion object {
        private const val locationRequestCode = 100
        private const val newReminderReqCode = 101

        private const val defaultZoom = 15
        private val TAG = WhileYoureOut::class.java.simpleName

    }



    @RequiresApi(Build.VERSION_CODES.Q)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        val mapFragment = supportFragmentManager
            .findFragmentById(R.id.map) as SupportMapFragment
        mapFragment.getMapAsync(this)

        // Construct a FusedLocationProviderClient.
        fusedLocationProviderClient = LocationServices.getFusedLocationProviderClient(this)



        val newReminderFAB = findViewById<FloatingActionButton>(R.id.newReminder)
        val getLocationFAB = findViewById<FloatingActionButton>(R.id.currentLocation)

        showReminders()

        newReminder.visibility = View.VISIBLE
        currentLocation.visibility = View.VISIBLE
        getLocationFAB.setOnClickListener{
            getDeviceLocation()
        }
        newReminderFAB.setOnClickListener {
            map?.run {
                startActivityForResult(mainIntent(
                    this@WhileYoureOut, cameraPosition.target,
                    cameraPosition.zoom)
                    ,newReminderReqCode
                )
            }
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == newReminderReqCode && resultCode == RESULT_OK) {
            showReminders()

            val reminder = getRepository().getLast()
            map?.moveCamera(CameraUpdateFactory.newLatLngZoom(reminder?.latLng, 15f))

            Snackbar.make(main, R.string.reminder_added, Snackbar.LENGTH_LONG).show()
        }
    }


    fun mainIntent(context: Context, latLng: LatLng, zoom: Float): Intent {
        val mainIntent = Intent(context, CreateNewReminder::class.java)
        mainIntent
            .putExtra("mainLatLng", latLng)
            .putExtra("lat", latLng.latitude.toString())
            .putExtra("lon", latLng.longitude.toString())
            .putExtra("mainZoom", zoom.toString())
        return mainIntent
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        if (requestCode == locationRequestCode) {
            onMapAndPermissionReady()
        }
    }

    private fun onMapAndPermissionReady() {
        if (ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_FINE_LOCATION
            )
            == PackageManager.PERMISSION_GRANTED
        ) {
            map?.isMyLocationEnabled = false
            newReminder.visibility = View.VISIBLE
            currentLocation.visibility = View.VISIBLE
        }
    }

    private fun showReminders() {
        map?.run {
            clear()
            for (reminder in getRepository().getAll()) {
                showReminderInMap(this@WhileYoureOut, this, reminder)
            }
        }
    }

    override fun onMapReady(googleMap: GoogleMap) {
        map = googleMap
        map?.run {
            uiSettings.isMyLocationButtonEnabled = false
            uiSettings.isMapToolbarEnabled = false
            setOnMarkerClickListener(this@WhileYoureOut)
        }

        getLocationPermission()
        updateLocationUI()
        getDeviceLocation()

    }

    override fun onMarkerClick(marker: Marker): Boolean {
        val reminder = getRepository().get(marker.tag as String)

        if (reminder != null) {
            showRemoveAlert(reminder)
        }

        return true
    }
/*

    private fun autoLocate(){

        var locationManager: LocationManager =
            this.getSystemService(Context.LOCATION_SERVICE) as LocationManager

        // gets current location and zooms to it
        val bestProvider = locationManager.getBestProvider(Criteria(), false)
        val location = bestProvider?.let { it1 -> locationManager.getLastKnownLocation(it1) }
        if (location != null) {
            val latLng = LatLng(location.latitude, location.longitude)
            map?.animateCamera(CameraUpdateFactory.newLatLngZoom(latLng, 15f))
        }

        locationManager = getSystemService(Context.LOCATION_SERVICE) as LocationManager

        if (ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_FINE_LOCATION
            )
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION),
                locationRequestCode
            )
        }
        if (ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_BACKGROUND_LOCATION
            )
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION),
                locationRequestCode
            )
        }
    }*/

    private fun showRemoveAlert(reminder: Reminder) {
        val alertDialog = AlertDialog.Builder(this).create()
        alertDialog.run {
            setMessage(getString(R.string.removal_warning))
            setButton(
                AlertDialog.BUTTON_POSITIVE,
                getString(R.string.remove)
            ) { dialog, _ ->
                removeReminder(reminder)
                dialog.dismiss()
            }
            setButton(
                AlertDialog.BUTTON_NEGATIVE,
                getString(R.string.cancel)
            ) { dialog, _ ->
                dialog.dismiss()
            }
            show()
        }
    }

    private fun removeReminder(reminder: Reminder) {
        getRepository().remove(
            reminder,
            success = {
                showReminders()
                Snackbar.make(main, R.string.reminder_removed, Snackbar.LENGTH_LONG).show()
            },
            failure = {
                Snackbar.make(main, it, Snackbar.LENGTH_LONG).show()
            })
    }


    private fun getDeviceLocation() {
        /*
         * Get the best and most recent location of the device, which may be null in rare
         * cases when a location is not available.
         */
        try {
            if (locationPermissionGranted) {
                val locationResult = fusedLocationProviderClient.lastLocation
                locationResult.addOnCompleteListener(this) { task ->
                    if (task.isSuccessful) {
                        // Set the map's camera position to the current location of the device.
                        lastKnownLocation = task.result
                        if (lastKnownLocation != null) {
                            map?.moveCamera(CameraUpdateFactory.newLatLngZoom(
                                LatLng(lastKnownLocation!!.latitude,
                                    lastKnownLocation!!.longitude), defaultZoom.toFloat()))
                        }
                    } else {
                        Log.d(TAG, "Current location is null. Using defaults.")
                        Log.e(TAG, "Exception: %s", task.exception)
                        map?.moveCamera(CameraUpdateFactory
                            .newLatLngZoom(defaultLocation, defaultZoom.toFloat()))
                        map?.uiSettings?.isMyLocationButtonEnabled = false
                    }
                }
            }
        } catch (e: SecurityException) {
            Log.e("Exception: %s", e.message, e)
        }
    }

    private fun getLocationPermission() {
        /*
         * Request location permission, so that we can get the location of the
         * device. The result of the permission request is handled by a callback,
         * onRequestPermissionsResult.
         */
        if (ContextCompat.checkSelfPermission(this.applicationContext,
                Manifest.permission.ACCESS_FINE_LOCATION)
            == PackageManager.PERMISSION_GRANTED) {
            locationPermissionGranted = true
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.ACCESS_FINE_LOCATION),
                PERMISSIONS_REQUEST_ACCESS_FINE_LOCATION
            )
        }
    }



    /**
     * Updates the map's UI settings based on whether the user has granted location permission.
     */
    // [START maps_current_place_update_location_ui]
    private fun updateLocationUI() {
        try {
            if (locationPermissionGranted) {
                map?.isMyLocationEnabled = true
                map?.uiSettings?.isMyLocationButtonEnabled = true
            } else {
                map?.isMyLocationEnabled = false
                map?.uiSettings?.isMyLocationButtonEnabled = false
                lastKnownLocation = null
                getLocationPermission()
            }
        } catch (e: SecurityException) {
            Log.e("Exception: %s", e.message, e)
        }
    }

    override fun onCameraIdle() {
        map?.cameraPosition?.target
    }
}