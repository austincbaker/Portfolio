package com.company;

import java.util.Comparator;

public class compareCircles implements Comparator<Circle> {
    public int compare(Circle c1, Circle c2) {
        return Integer.compare(c1.getRadius(), c2.getRadius());
    }
}
