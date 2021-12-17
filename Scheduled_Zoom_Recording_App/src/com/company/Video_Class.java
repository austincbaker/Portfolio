package com.company;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.time.LocalTime;

/**
 * Records the screen of the user by taking individual screenshots and stitching them together as one MP4 file
 */

public class Video_Class implements Runnable {
    private final LocalTime end_time;

    /**
     * Constructor for class
     *
     * @param end_time
     */
    public Video_Class(LocalTime end_time) {
        this.end_time = end_time;
    }

    /**
     * Starts the recording process
     *
     * @throws AWTException
     */

    public void run() {

        try {
            // Displaying the thread that is running

            Robot robot = new Robot();

            Rectangle screenSize = new Rectangle(Toolkit.getDefaultToolkit().getScreenSize());

            //int number_of_screenshots = 0;

            //String path;

            BufferedImage image;

            LocalTime currentTime = LocalTime.now();

            while (currentTime.isBefore(end_time)) {
                //currentTime = LocalTime.now();

                image = robot.createScreenCapture(screenSize);

                ImageIO.write(image, "jpeg", new File("C:\\RecorderProgram\\Screenshots\\" + LocalTime.now().toNanoOfDay() + ".jpeg"));

                //number_of_screenshots++;
                currentTime = LocalTime.now();

            }

            //f.deleteOnExit();
        } catch (IOException ioException) {
            System.out.println("IO Exception in " + Thread.currentThread() + " During file writing");
            ioException.printStackTrace();
        } catch (AWTException awtException) {
            System.out.println("AWT Exception in " + Thread.currentThread() + " Dealing with Robot");
            awtException.printStackTrace();
        }
    }
}