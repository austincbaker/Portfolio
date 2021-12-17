package com.company;

import javax.swing.*;
import java.awt.*;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.sql.*;
import java.util.ArrayList;

public class Prior_Meeting_Selection extends JDialog implements ActionListener {

    private static final String INSERT_SQL =
            "INSERT INTO meeting(matchID, meeting_name, meeting_ID, meeting_password, start_hour, start_minute, start_am_pm," +
                    " end_hour, end_minute, end_am_pm) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
    private final String match_ID;
    private String meeting_name;
    private String meeting_ID;
    private String meeting_password;

    private int starting_hour;
    private int starting_minute;
    private int starting_am_pm;

    private int ending_hour;
    private int ending_minute;
    private int ending_am_pm;

    public int new_meeting_created;

    private JComboBox meeting_selection_JBox;
    private ArrayList<Meeting> meeting_object_list;
    private final JButton Ok;
    private final JButton Cancel;
    private final JButton New_Meeting;
    private final Connection connection = DriverManager.getConnection("jdbc:sqlite:src/usersdb.db");

    /**
     * Class constructor which produces dialog and accesses database to let the user select their previous meetings
     * @param frame
     * @param meeting_object_list
     * @param matchID
     * @throws SQLException
     */
    protected Prior_Meeting_Selection(Frame frame, ArrayList<Meeting> meeting_object_list, String matchID) throws SQLException {
        super(frame, "Select a meeting", true);
        this.match_ID = matchID;
        if(meeting_object_list.isEmpty()){
            Create_New_Meeting();
            Add_To_DB();
            Meeting m = new Meeting(this.meeting_name, this.meeting_ID, this.meeting_password,
                    this.starting_hour, this.starting_minute, this.starting_am_pm, this.ending_hour
                    , this.ending_minute, this.ending_am_pm);
            meeting_object_list.add(m);
        }
        this.meeting_object_list = meeting_object_list;
        Point loc = frame.getLocation();
        setLocation(loc.x + 120, loc.y + 120);

        String[] meeting_name_list = new String[meeting_object_list.size()];
        for(int i = 0; i < meeting_object_list.size(); i++){
            String name = meeting_object_list.get(i).getMeetingName();
            meeting_name_list[i] = name;
        }

        JPanel panel = new JPanel();
        panel.setLayout(new GridBagLayout());
        GridBagConstraints gridBagConstraints = new GridBagConstraints();
        gridBagConstraints.insets = new Insets(5, 5, 5, 5);

        JLabel label = new JLabel("Select a meeting");
        gridBagConstraints.fill = GridBagConstraints.HORIZONTAL;
        gridBagConstraints.gridx = 0;
        gridBagConstraints.gridy = 0;
        panel.add(label, gridBagConstraints);

        meeting_selection_JBox = new JComboBox(meeting_name_list);
        gridBagConstraints.gridwidth = 1;
        gridBagConstraints.gridx = 1;
        gridBagConstraints.gridy = 0;
        panel.add(meeting_selection_JBox, gridBagConstraints);

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

        New_Meeting = new JButton("Add New");
        New_Meeting.addActionListener(this);
        gridBagConstraints.gridx = 4;
        gridBagConstraints.gridy = 4;
        panel.add(New_Meeting, gridBagConstraints);
        getContentPane().add(panel);

        pack();
        this.setVisible(true);
    }

    /**
     * Handles the user selecting OK, Cancel, or New Meeting in dialog
     * @param e
     */
    public void actionPerformed(ActionEvent e) {
        Object source = e.getSource();
        if (source == Cancel) {
            dispose();
            System.exit(0);
        }
        if (source == Ok) {
            this.meeting_name = String.valueOf(meeting_selection_JBox.getSelectedItem());
            for(int i = 0; i < this.meeting_object_list.size(); i++){
                if(this.meeting_object_list.get(i).getMeetingName().equals(this.meeting_name)){
                    this.meeting_ID = this.meeting_object_list.get(i).getMeetingID();
                    this.meeting_password = this.meeting_object_list.get(i).getMeetingPassword();
                    this.starting_hour = this.meeting_object_list.get(i).getStarting_hour();
                    this.starting_minute = this.meeting_object_list.get(i).getStarting_minute();
                    this.starting_am_pm = this.meeting_object_list.get(i).getStarting_am_pm();
                    this.ending_hour = this.meeting_object_list.get(i).getEnding_hour();
                    this.ending_minute = this.meeting_object_list.get(i).getEnding_minute();
                    this.ending_am_pm = this.meeting_object_list.get(i).getEnding_am_pm();
                }
            }
            System.out.println("OK pressed");
            System.out.println(this.meeting_name);
            System.out.println(this.meeting_ID);
            System.out.println(this.meeting_password);
            dispose();
            //System.exit(-1);
        }
        if(source == New_Meeting) {
            try {
                System.out.println("New Meeting Pressed");
                dispose();
                Meeting new_meeting  = Create_New_Meeting();
                this.meeting_object_list.add(new_meeting);
                this.new_meeting_created = 1;
                System.out.println("New Meeting added?");
                dispose();
            } catch (SQLException throwables) {
                throwables.printStackTrace();
            }
            dispose();
            return;
        }
        dispose();
    }

    /**
     * Creates a new meeting
     * @return The created meeting
     * @throws SQLException
     */

    public Meeting Create_New_Meeting() throws SQLException {
        this.meeting_name = String.valueOf(JOptionPane.showInputDialog("Enter the meeting name"));
        this.meeting_ID = String.valueOf(JOptionPane.showInputDialog("Enter the Meeting ID"));
        this.meeting_password = String.valueOf(JOptionPane.showInputDialog("Enter the Meeting Password"));
        Frame start_time_frame = new Frame();
        TimeSelection start_time_selection = new TimeSelection(start_time_frame, "Set Start Time");
        this.starting_hour = start_time_selection.getHour();
        this.starting_minute = start_time_selection.getMinute();
        this.starting_am_pm = start_time_selection.getAmpm();

        //Creates a new instance of the Time Selection Class to get the JBox so a user can set an end time
        Frame end_time_frame = new Frame();
        TimeSelection end_time_selection = new TimeSelection(end_time_frame, "Set End Time");
        this.ending_hour = end_time_selection.getHour();
        this.ending_minute = end_time_selection.getMinute();
        this.ending_am_pm = end_time_selection.getAmpm();

        Meeting new_meeting = new Meeting(meeting_name, meeting_ID, meeting_password, starting_hour,
                starting_minute, starting_am_pm, ending_hour, ending_minute, ending_am_pm);

        Add_To_DB();
        dispose();
        return new_meeting;
    }

    /**
     * Adds a new meeting to the database
     * @return Number of rows inserted to the database
     */
    public int Add_To_DB() {
        int numRowsInserted = 0;
        PreparedStatement preparedStatement = null;
        try {
            preparedStatement = this.connection.prepareStatement(INSERT_SQL);
            preparedStatement.setString(1, this.match_ID);
            preparedStatement.setString(2, this.meeting_name);
            preparedStatement.setString(3, this.meeting_ID);
            preparedStatement.setString(4, this.meeting_password);

            preparedStatement.setInt(5, this.starting_hour);
            preparedStatement.setInt(6, this.starting_minute);
            preparedStatement.setInt(7, this.starting_am_pm);

            preparedStatement.setInt(8, this.ending_hour);
            preparedStatement.setInt(9, this.ending_minute);
            preparedStatement.setInt(10, this.ending_am_pm);
            numRowsInserted = preparedStatement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        } finally {
            close(preparedStatement);

        }
        System.out.println(numRowsInserted + "Rows inserted, added to DB");
        return numRowsInserted;
    }

    /**
     * Closes the database access from Add_To_DB
     * @param statement
     */
    private void close(Statement statement)  {
        try {
            if (statement != null) {
                statement.close();
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    public String getMeeting_name(){
        return this.meeting_name;
    }

    public String getMeeting_ID(){
        return this.meeting_ID;
    }

    public String getMeeting_password(){
        return this.meeting_password;
    }

    public int getStarting_hour() {
        return starting_hour;
    }

    public int getStarting_minute() {
        return starting_minute;
    }

    public int getStarting_am_pm() {
        return starting_am_pm;
    }

    public int getEnding_hour() {
        return ending_hour;
    }

    public int getEnding_minute() {
        return ending_minute;
    }

    public int getEnding_am_pm() {
        return ending_am_pm;
    }
}
