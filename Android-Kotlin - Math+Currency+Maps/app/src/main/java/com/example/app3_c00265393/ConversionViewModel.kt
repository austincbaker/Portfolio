package com.example.app3_c00265393

import androidx.lifecycle.ViewModel

class ConversionViewModel : ViewModel() {
    private var europe = true
    private var dollars = ""
    private val eurosRate = 0.90583
    private var euros = 0.0
    private val poundsRate = 0.81367
    private var pounds = 0.0

    fun setConversionAmount(us: String){
        val dollars = us.toFloat()
        euros = dollars * eurosRate
        pounds = dollars * poundsRate
    }

    fun getConversionAmount(): String?{
        var output : String

        if(europe){
            output = "" + euros + " Euros"
            europe = false
        } else {
            output = "" + pounds + " Pounds"
            europe = true
        }
        return output
    }
}