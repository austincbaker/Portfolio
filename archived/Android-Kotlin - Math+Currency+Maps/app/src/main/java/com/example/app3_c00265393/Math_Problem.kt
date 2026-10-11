package com.example.app3_c00265393

import android.os.Bundle
import androidx.fragment.app.Fragment
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import kotlinx.android.synthetic.main.fragment_math__problem.*
import kotlin.random.Random

// TODO: Rename parameter arguments, choose names that match
// the fragment initialization parameters, e.g. ARG_ITEM_NUMBER
private const val ARG_PARAM1 = "param1"
private const val ARG_PARAM2 = "param2"


/**
 * A simple [Fragment] subclass.
 * Use the [Math_Problem.newInstance] factory method to
 * create an instance of this fragment.
 */
class Math_Problem : Fragment() {
    // TODO: Rename and change types of parameters
    private var param1: String? = null
    private var param2: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        arguments?.let {
            param1 = it.getString(ARG_PARAM1)
            param2 = it.getString(ARG_PARAM2)
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        println("Before V")
        val v = inflater.inflate(R.layout.fragment_math__problem, container, false)
        println("after V")
        val buttonA: Button? = v?.findViewById(R.id.createNewDisplay)
        val buttonB: Button? = v?.findViewById(R.id.buttonToShowAnswer)
        var x = setX()
        var y = setY()
        var op = setOP()
        println("after buttonA")
        if (buttonA != null) {
            buttonA.setOnClickListener {
                changeEq(v)
            }
        }
        if (buttonB != null && userAnswerInput != null) {
            buttonB.setOnClickListener {
                val ans = answer(x, y, op)
                displayAnswer(ans)
            }
        } else {
            println("Button A is Null")
        }
        return v
    }

    companion object {
        /**
         * Use this factory method to create a new instance of
         * this fragment using the provided parameters.
         *
         * @param param1 Parameter 1.
         * @param param2 Parameter 2.
         * @return A new instance of fragment Math_Problem.
         */
        // TODO: Rename and change types and number of parameters
        @JvmStatic
        fun newInstance(param1: String, param2: String) =
            Math_Problem().apply {
                arguments = Bundle().apply {
                    putString(ARG_PARAM1, param1)
                    putString(ARG_PARAM2, param2)
                }
            }
    }

    fun setX(): Int {
        val x = Random.nextInt(-100, 100)
        return x
    }

    fun setY(): Int {
        val y = Random.nextInt(-100, 100)
        return y
    }

    fun setOP(): Int {
        val op = Random.nextInt(0, 5)
        return op
    }

    fun setDisplay(view: View?, x: Int, y: Int, op: Int): Boolean {
        firstNumber.text = x.toString()
        operatorView.text = operatorChange(op).toString()
        secondNumber.text = y.toString()
        return true
    }

    fun operatorChange(operatorValue: Int): Char {
        return when (operatorValue) {
            0 -> '+'
            1 -> '-'
            2 -> '*'
            3 -> '/'
            4 -> '%'
            else -> 'z'
        }
    }

    fun answer(numOne: Int, numTwo: Int, operatorValue: Int): Double {
        return when (operatorValue) {
            0 -> numOne.plus(numTwo).toDouble()
            1 -> numOne.minus(numTwo).toDouble()
            2 -> numOne.times(numTwo).toDouble()
            3 -> (numOne / numTwo).toDouble()
            4 -> numOne.rem(numTwo).toDouble()
            else -> -99999999.9999999
        }
    }

    fun displayAnswer(ans: Double) {
        if (userAnswerInput.text == null) {

        }
        else {
            var ua = userAnswerInput.text.toString().toDouble()
            if (ua == ans) {
                answerDisplay.text = ans.toString() + " Correct!"
            } else {
                answerDisplay.text = ans.toString() + " Incorrect!"
            }
        }
    }

    fun changeEq(v: View) {
        val buttonA: Button? = v?.findViewById(R.id.createNewDisplay)
        val buttonB: Button? = v?.findViewById(R.id.buttonToShowAnswer)
        var x = setX()
        var y = setY()
        var op = setOP()
        println("after buttonA")
        if (buttonA != null) {
            buttonA.setOnClickListener {
                println("Before something")
                setDisplay(v, x, y, op)
                println("After somethingV")
                buttonA.setOnClickListener {
                    changeEq(v)
                }
            }
        }
        if (buttonB != null && userAnswerInput != null) {
            buttonB.setOnClickListener {
                val ans = answer(x, y, op)
                displayAnswer(ans)
            }
        } else {
            println("Button A is Null")
        }
    }
}