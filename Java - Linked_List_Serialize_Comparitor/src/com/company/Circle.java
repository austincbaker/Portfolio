package com.company;

import java.io.Serializable;

public class Circle implements Serializable {
    private int radius = 1;
    private String name;

    public Circle(){

    }

    public Circle(int rad) {
        if (rad > 0) {
            setRadius(rad);
        }
    }

    public int getRadius() {
        return this.radius;
    }

    public void setRadius(int radius) {
        if (radius > 0) {
            this.radius = radius;
        } else {
            System.out.println("The radius of the circle must be greater than 0. Default radius is set to 1.");
            this.radius = 1;
        }
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    @Override
    public String toString(){
        return ("The radius of circle " + getName() + " is " + getRadius());
    }
}