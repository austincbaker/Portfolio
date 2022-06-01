// Program Description: This program gives the tine it takes to traverse a linked list via iterator and get(index),
// it uses a Stack to solve postfix equations entered as strings, implements the interfaces Serialize and Compare in
// class Circle, and implements a generic method to sort at least 5 circles by their radius.

package com.company;

import java.util.*;

public class Main {

    public static void intList() {

        int listSize = 100000;

        LinkedList<Integer> list = new LinkedList<>();
        for (int i = 0; i < listSize; i++) {
            double num = Math.random() * 100;
            int number = (int) num;
            list.add(number);
        }
        int i = 0;
        System.out.println("Working...");
        long start = System.currentTimeMillis();
        for (Integer integer : list) {
            i++;
        }
        long endTime = System.currentTimeMillis();
        long executionTime = endTime - start;
        System.out.println("Using an iterator, it took " + executionTime + "ms to process the linked list.");

        System.out.println("Working...");
        start = System.currentTimeMillis();
        for (i = 0; i < listSize; i++) {
            list.get(i);
        }
        endTime = System.currentTimeMillis();
        executionTime = endTime - start;
        System.out.println("Using get(index), it took " + executionTime + "ms to process the linked list.\n");
    }

    /*
     * Helper method for postfix to assist with preforming the correct operation
     * via the given doubles and char
     * */
    public static Double eval(Double a, Double b, String c) {
        if (c.equals("+")) {
            return b + a;
        } else if (c.equals("-")) {
            return b - a;
        } else if (c.equals("*")) {
            return a * b;
        } else {
            return b / a;
        }
    }

    /*
     * Takes a postfix string of an equation, deciphers the operators and operands,
     * sends the decoded strings to a helper class and returns the answer for the
     * given equation
     * */
    public static void postfix(String s) {
        Stack<Double> stack = new Stack<>();
        String[] st = s.split(" ");
        ArrayList<String> temp = new ArrayList<>();
        for (int i = 0; i < st.length; i++) {
            if (st[i].equals("+") || st[i].equals("-") || st[i].equals("*") || st[i].equals("/")) {
                double a = stack.pop();
                double b = stack.pop();
                stack.push(eval(a, b, st[i]));
            } else {
                stack.push(Double.parseDouble(st[i]));
            }
        }
        System.out.println(stack.pop());
    }

    /*
     * Sorts the list using the created comparator class using a bubble sort (O(n^2)).
     * */
    public static <E> void aSort(E[] list, Comparator<? super E> comparator) {
        for (int i = 0; i < list.length; i++) {
            for (int j = list.length - 1; j > 0; j--) {
                if (comparator.compare(list[j], list[j - 1]) < 0) {
                    E temp = list[j];
                    list[j] = list[j - 1];
                    list[j - 1] = temp;
                }
            }
        }
        for (Object o : list) {
            System.out.println(o);
        }
    }

    public static void main(String[] args) {
        intList();
        String s = "2 3 + ";
        System.out.print("2 3 + = \t");
        postfix(s);
        System.out.println("");
        s = "5.0 3.5 - 1.2 / ";
        System.out.print("5.0 3.5 - 1.2 / = \t");
        postfix(s);
        System.out.println("");
        s = "5.0 3.5 1.2 - / ";
        System.out.print("5.0 3.5 1.2 - / = \t");
        postfix(s);

        /*
         * Creates Circle objects
         * */
        Circle[] cList = new Circle[10];
        Circle c1 = new Circle((int) (Math.random() * 100));
        c1.setName("a");
        Circle c2 = new Circle((int) (Math.random() * 100));
        c2.setName("b");
        Circle c3 = new Circle((int) (Math.random() * 100));
        c3.setName("c");
        Circle c4 = new Circle((int) (Math.random() * 100));
        c4.setName("d");
        Circle c5 = new Circle((int) (Math.random() * 100));
        c5.setName("e");
        Circle c6 = new Circle((int) (Math.random() * 100));
        c6.setName("f");
        Circle c7 = new Circle((int) (Math.random() * 100));
        c7.setName("g");
        Circle c8 = new Circle((int) (Math.random() * 100));
        c8.setName("h");
        Circle c9 = new Circle((int) (Math.random() * 100));
        c9.setName("i");
        Circle c10 = new Circle((int) (Math.random() * 100));
        c10.setName("j");

        /*
         * Adds objects to the created list
         * */
        cList[0] = c1;
        cList[1] = c2;
        cList[2] = c3;
        cList[3] = c4;
        cList[4] = c5;
        cList[5] = c6;
        cList[6] = c7;
        cList[7] = c8;
        cList[8] = c9;
        cList[9] = c10;

        /*
         * Creates a new comparator object to be passed through the sort function
         * */
        compareCircles comp = new compareCircles();
        System.out.println("\nPre-sort: ");
        for (Circle c : cList) {
            System.out.println(c.toString());
        }
        System.out.println("");
        System.out.println("Post-sort: ");
        aSort(cList, comp);
    }
}
