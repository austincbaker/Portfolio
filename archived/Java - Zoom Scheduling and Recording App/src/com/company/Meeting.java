package com.company;

public class Meeting {

    private String meetingName;
    private String meetingID;
    private String meetingPassword;
    private int starting_hour;
    private int starting_minute;
    private int starting_am_pm;
    private int ending_hour;
    private int ending_minute;
    private int ending_am_pm;

    /**
     * Generalized Constructor
     */

    public Meeting(){}

    /**
     * Parameterized Constructor
     * @param meetingName
     * @param meetingID
     * @param meetingPassword
     * @param starting_hour
     * @param starting_minute
     * @param starting_am_pm
     * @param ending_hour
     * @param ending_minute
     * @param ending_am_pm
     */
    public Meeting(String meetingName, String meetingID, String meetingPassword, int starting_hour, int starting_minute,
                   int starting_am_pm, int ending_hour, int ending_minute, int ending_am_pm) {
        this.meetingName = meetingName;
        this.meetingID = meetingID;
        this.meetingPassword = meetingPassword;
        this.starting_hour = starting_hour;
        this.starting_minute = starting_minute;
        this.starting_am_pm = starting_am_pm;
        this.ending_hour = ending_hour;
        this.ending_minute = ending_minute;
        this.ending_am_pm = ending_am_pm;
    }


    public String getMeetingName() {
        return meetingName;
    }

    public void setMeetingName(String meetingName) {
        this.meetingName = meetingName;
    }

    public String getMeetingID() {
        return meetingID;
    }

    public void setMeetingID(String meetingID) {
        this.meetingID = meetingID;
    }

    public String getMeetingPassword() {
        return meetingPassword;
    }

    public void setMeetingPassword(String meetingPassword) {
        this.meetingPassword = meetingPassword;
    }

    public int getStarting_hour() {
        return starting_hour;
    }

    public void setStarting_hour(int starting_hour) {
        this.starting_hour = starting_hour;
    }

    public int getStarting_minute() {
        return starting_minute;
    }

    public void setStarting_minute(int starting_minute) {
        this.starting_minute = starting_minute;
    }

    public int getStarting_am_pm() {
        return starting_am_pm;
    }

    public void setStarting_am_pm(int starting_am_pm) {
        this.starting_am_pm = starting_am_pm;
    }

    public int getEnding_hour() {
        return ending_hour;
    }

    public void setEnding_hour(int ending_hour) {
        this.ending_hour = ending_hour;
    }

    public int getEnding_minute() {
        return ending_minute;
    }

    public void setEnding_minute(int ending_minute) {
        this.ending_minute = ending_minute;
    }

    public int getEnding_am_pm() {
        return ending_am_pm;
    }

    public void setEnding_am_pm(int ending_am_pm) {
        this.ending_am_pm = ending_am_pm;
    }
}

