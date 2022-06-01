package com.example.app3_c00265393

import androidx.lifecycle.ViewModelProviders
import android.os.Bundle
import androidx.fragment.app.Fragment
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import kotlinx.android.synthetic.main.fragment_conversion.*

class Conversion : Fragment() {

    companion object {
        fun newInstance() = Conversion()
    }

    private lateinit var viewModel: ConversionViewModel

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        return inflater.inflate(R.layout.fragment_conversion, container, false)
    }

    override fun onActivityCreated(savedInstanceState: Bundle?) {
        super.onActivityCreated(savedInstanceState)
        viewModel = ViewModelProviders.of(this).get(ConversionViewModel::class.java)
        conversionToggle.setOnClickListener{
            if (dollarsEntry.text.isNotEmpty()) {
                viewModel.setConversionAmount(dollarsEntry.text.toString())
                conversionOutput.text = viewModel.getConversionAmount()
            } else {
                conversionOutput.text = "Nuttin'"
            }
        }
    }

}