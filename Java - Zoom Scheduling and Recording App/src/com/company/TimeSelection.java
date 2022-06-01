package com.company;

import javax.swing.*;
import java.awt.*;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;

public class TimeSelection extends JDialog implements ActionListener {
    private int hour;
    private int minute;
    private int ampm;
    protected Integer[] time_selected;
    private JComboBox<String> Jhour;
    private JComboBox<String> Jminutes;
    private JComboBox<String> Jampm;
    private JButton Ok;
    private JButton Cancel;

    /**
     * Class Constructor which generates a dialog box so the user can set the  start/ end time of the meeting
     * @param frame
     * @param title
     */

    protected TimeSelection(Frame frame, String title) {
        super(frame, title, true);
        String[] hr = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"};
        String[] min = new String[60];
        for (int i = 0; i < 60; i++) {
            min[i] = String.valueOf(i);
        }
        String[] ap = {"AM", "PM"};
        Point loc = frame.getLocation();
        setLocation(loc.x + 120, loc.y + 120);
        time_selected = new Integer[3]; // set to amount of Jbox items

        JPanel panel = new JPanel();
        panel.setLayout(new GridBagLayout());
        GridBagConstraints gridBagConstraints = new GridBagConstraints();
        gridBagConstraints.insets = new Insets(5, 5, 5, 5);

        JLabel hourLabel = new JLabel("Hour:");
        gridBagConstraints.fill = GridBagConstraints.HORIZONTAL;
        gridBagConstraints.gridx = 0;
        gridBagConstraints.gridy = 0;
        panel.add(hourLabel, gridBagConstraints);

        Jhour = new JComboBox<>(hr);
        gridBagConstraints.gridwidth = 1;
        gridBagConstraints.gridx = 1;
        gridBagConstraints.gridy = 0;
        panel.add(Jhour, gridBagConstraints);

        JLabel minLabel = new JLabel("Minutes:");
        gridBagConstraints.gridwidth = 1;
        gridBagConstraints.gridx = 2;
        gridBagConstraints.gridy = 0;
        panel.add(minLabel, gridBagConstraints);

        Jminutes = new JComboBox<>(min);
        gridBagConstraints.gridwidth = 1;
        gridBagConstraints.gridx = 3;
        gridBagConstraints.gridy = 0;
        panel.add(Jminutes, gridBagConstraints);

        JLabel ampmLabel = new JLabel("AM/PM:");
        gridBagConstraints.gridwidth = 1;
        gridBagConstraints.gridx = 4;
        gridBagConstraints.gridy = 0;
        panel.add(ampmLabel, gridBagConstraints);

        Jampm = new JComboBox<>(ap);
        gridBagConstraints.gridwidth = 1;
        gridBagConstraints.gridx = 5;
        gridBagConstraints.gridy = 0;

        panel.add(Jampm, gridBagConstraints);
        JLabel spacer = new JLabel(" ");
        gridBagConstraints.gridx = 0;
        gridBagConstraints.gridy = 2;
        panel.add(spacer, gridBagConstraints);

        Ok = new JButton("Ok");
        Ok.addActionListener(this);
        gridBagConstraints.gridwidth = 1;
        gridBagConstraints.gridx = 2;
        gridBagConstraints.gridy = 4;
        panel.add(Ok, gridBagConstraints);

        Cancel = new JButton("Cancel");
        Cancel.addActionListener(this);
        gridBagConstraints.gridx = 3;
        gridBagConstraints.gridy = 4;
        panel.add(Cancel, gridBagConstraints);
        getContentPane().add(panel);

        pack();
        this.setVisible(true);
    }

    /**
     * Handles the user choosing Ok or Cancel
     * @param e
     */
    public void actionPerformed(ActionEvent e) {
        Object source = e.getSource();
        if (source == Cancel) {
            System.exit(0);
        }
        if (source == Ok) {
            this.hour = time_selected[0] = Integer.valueOf(String.valueOf(Jhour.getSelectedItem()));
            this.minute = time_selected[1] = Integer.valueOf(String.valueOf(Jminutes.getSelectedItem()));
            //If the AM is selected, and the hour selected was 12, it is converted to 00 hours, or 12am.
            if (Jampm.getSelectedItem() == "AM") {
                this.ampm = time_selected[2] = 0;
                if (time_selected[0] == 12) {
                    this.hour = time_selected[0] = 0;
                }

            } else {
                //If PM is selected, 12 is added to the selection to make it correct for UTC.
                // If the time equals 24 (or 12+12), the time is set back to 12pm, or noon.
                this.ampm = time_selected[2] = 1;
                this.hour = time_selected[0] += 12;// adds 12 hours to the time since it is PM.
                if (time_selected[0] == 24) {
                    this.hour = time_selected[0] = 12;
                }
            }
        }
        dispose();
    }

    public int getHour() {
        return this.hour;
    }

    public int getMinute() {
        return this.minute;
    }

    public void setMinute(int minute) {
        this.minute = minute;
    }

    public int getAmpm() {
        return this.ampm;
    }

    public void setAmpm(int ampm) {
        this.ampm = ampm;
    }
}
