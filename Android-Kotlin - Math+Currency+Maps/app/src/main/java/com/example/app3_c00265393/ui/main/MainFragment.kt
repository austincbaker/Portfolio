package com.example.app3_c00265393.ui.main

import androidx.lifecycle.ViewModelProviders
import android.os.Bundle
import androidx.fragment.app.Fragment
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.navigation.Navigation
import com.example.app3_c00265393.R
import kotlinx.android.synthetic.main.main_fragment.*
import kotlin.random.Random

class MainFragment : Fragment() {

    companion object {
        fun newInstance() = MainFragment()
    }

    private lateinit var viewModel: MainViewModel

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        return inflater.inflate(R.layout.main_fragment, container, false)
    }

    override fun onActivityCreated(savedInstanceState: Bundle?) {
        super.onActivityCreated(savedInstanceState)
        viewModel = ViewModelProviders.of(this).get(MainViewModel::class.java)
        toWebsite.setOnClickListener {
            Navigation.findNavController(it).navigate(
                R.id.websiteDisplay
            )
        }
        toConversion.setOnClickListener {
            Navigation.findNavController(it).navigate(
                R.id.conversionDisplay
            )
        }
        toMap.setOnClickListener {
            Navigation.findNavController(it).navigate(
                R.id.mapDisplay
            )
        }
        mathButton.setOnClickListener{
            Navigation.findNavController(it).navigate(
                R.id.math_Problem
            )
        }

    }
}