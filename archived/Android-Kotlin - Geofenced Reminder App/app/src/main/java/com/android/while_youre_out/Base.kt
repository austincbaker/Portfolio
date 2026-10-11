package com.android.while_youre_out


import androidx.appcompat.app.AppCompatActivity

abstract class Base : AppCompatActivity() {
    // Starts the repository
    fun getRepository() = (application as ReminderApp).getRepository()
}