package com.company;

import java.awt.*;
import java.awt.datatransfer.Clipboard;
import java.awt.datatransfer.StringSelection;
import java.awt.image.BufferedImage;
import java.io.*;
import java.net.URISyntaxException;
import java.security.NoSuchAlgorithmException;
import java.security.spec.InvalidKeySpecException;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.Objects;
import javax.imageio.ImageIO;
import javax.sound.sampled.LineUnavailableException;
import javax.swing.*;
import org.jcodec.api.awt.AWTSequenceEncoder;

public class Main {


    public static void fileVerify() throws IOException {
        File f = new File("C:\\RecorderProgram");
        boolean path_check = f.exists();
        if (!path_check) {
            f.mkdir();
            Process p = Runtime.getRuntime().exec("xcopy /E /I Zoom_Recording_App/FFmpeg_Files C:\\RecorderProgram");
        }
        f = new File("C:\\RecorderProgram\\Audio");
        path_check = f.exists();
        if (!path_check) {
            f.mkdir();
        }
        f = new File("C:\\RecorderProgram\\SoundlessVideo");
        path_check = f.exists();
        if (!path_check) {
            f.mkdir();
        }
        f = new File("C:\\RecorderProgram\\FinalVideo");
        path_check = f.exists();
        if (!path_check) {
            f.mkdir();
        }
        f = new File("C:\\RecorderProgram\\Screenshots");
        path_check = f.exists();
        if (!path_check) {
            f.mkdir();
        }
        f = new File("C:\\RecorderProgram\\testPub\\");
        path_check = f.exists();
        if (!path_check) {
            Process p = Runtime.getRuntime().exec("xcopy /E /I Zoom_Recording_App\\testPub C:\\RecorderProgram");
        }
    }

    public static synchronized void User_Login() {
        final JFrame frame = new JFrame("User Login");
        JButton login_button = new JButton("Click to login");
        frame.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);
        frame.setSize(300, 100);
        frame.setLayout(new FlowLayout());
        frame.getContentPane().add(login_button);
        frame.setVisible(true);
        login_button.addActionListener(e -> {
            boolean move_on = false;
            User_Login user_login = new User_Login(frame);
            user_login.setVisible(true);

            while (!move_on) {
                if (user_login.Login_Successful()) {
                    //String username = user_login.getUsername();
                    //String password = user_login.getPassword();
                    String match_ID = user_login.getMatchID();
                    frame.dispose();

                    try {
                        After_Login(match_ID);
                    } catch (Exception ioException) {
                        ioException.printStackTrace();
                        move_on = true;
                    }
                }
            }

        });
    }

    private static ArrayList<Meeting> Gather_User_Meetings_From_DB(String match_ID) {
        String jdbcURL = "jdbc:sqlite:src/usersdb.db";
        ArrayList<Meeting> meeting_object_list = new ArrayList<>();

        try {
            Connection connection = DriverManager.getConnection(jdbcURL);
            String meeting_table = "SELECT * FROM meeting ORDER BY matchID";
            Statement statement = connection.createStatement();
            ResultSet meeting_table_result = statement.executeQuery(meeting_table);
            int matchID_from_DB = Integer.parseInt(meeting_table_result.getString(1));
            int matchID = Integer.parseInt(match_ID);

            while (meeting_table_result.next()) {
                matchID_from_DB = Integer.parseInt(meeting_table_result.getString(1));
                if (matchID_from_DB == matchID) {
                    Meeting meeting_object = new Meeting();
                    meeting_object.setMeetingName(meeting_table_result.getString(2));
                    meeting_object.setMeetingID(meeting_table_result.getString(3));
                    meeting_object.setMeetingPassword(meeting_table_result.getString(4));
                    meeting_object.setStarting_hour(meeting_table_result.getInt(5));
                    meeting_object.setStarting_minute(meeting_table_result.getInt(6));
                    meeting_object.setStarting_am_pm(meeting_table_result.getInt(7));
                    meeting_object.setEnding_hour(meeting_table_result.getInt(8));
                    meeting_object.setEnding_minute(meeting_table_result.getInt(9));
                    meeting_object.setEnding_am_pm(meeting_table_result.getInt(10));
                    meeting_object_list.add(meeting_object);
                }
            }
        } catch (SQLException sqlException) {
            System.out.println("Unable to connect to the database");
            sqlException.printStackTrace();
        }

        return meeting_object_list;
    }

    public static Meeting priorMeetingSelector(ArrayList<Meeting> meeting_object_list, String matchID) throws SQLException {
        Frame frame = new Frame();
        Prior_Meeting_Selection prior_meeting_selection = new Prior_Meeting_Selection(frame, meeting_object_list, matchID);
        if (prior_meeting_selection.new_meeting_created == 1) {
            meeting_object_list = Gather_User_Meetings_From_DB(matchID);
            frame.dispose();
            frame = new Frame();
            prior_meeting_selection = new Prior_Meeting_Selection(frame, meeting_object_list, matchID);
        }

        Meeting meeting = new Meeting();
        meeting.setMeetingName(prior_meeting_selection.getMeeting_name());
        meeting.setMeetingID(prior_meeting_selection.getMeeting_ID());
        meeting.setMeetingPassword(prior_meeting_selection.getMeeting_password());
        meeting.setStarting_hour(prior_meeting_selection.getStarting_hour());
        meeting.setStarting_minute(prior_meeting_selection.getStarting_minute());
        meeting.setStarting_am_pm(prior_meeting_selection.getStarting_am_pm());
        meeting.setEnding_hour(prior_meeting_selection.getEnding_hour());
        meeting.setEnding_minute(prior_meeting_selection.getEnding_minute());
        meeting.setEnding_am_pm(prior_meeting_selection.getEnding_am_pm());
        frame.dispose();
        return meeting;
    }

    public static void Error_Box(String infoMessage, String titleBar) {
        JOptionPane.showMessageDialog(null, infoMessage, "InfoBox" + titleBar, JOptionPane.INFORMATION_MESSAGE);
    }

    static int partition(ArrayList<String> file, int begin, int end) {
        int counter = begin;

        for (int i = begin; i < end; ++i) {
            String time1 = (file.get(i));
            String pivotTime = (file.get(end));
            if (time1.compareToIgnoreCase(pivotTime) < 0) {
                String temp = file.get(counter);
                file.set(counter, file.get(i));
                file.set(i, temp);
                ++counter;
            }
        }

        String temp = file.get(end);
        file.set(end, file.get(counter));
        file.set(counter, temp);
        return counter;
    }

    public static void quickSort(ArrayList<String> file, int begin, int end) {
        if (end > begin) {
            int pivot = partition(file, begin, end);
            quickSort(file, begin, pivot - 1);
            quickSort(file, pivot + 1, end);
        }
    }

    public static void createMP4(String videoName, int seconds) throws IOException {
        File screenshotsFolder = new File("C:\\RecorderProgram\\Screenshots");
        File mp4Folder = new File("C:\\RecorderProgram\\SoundlessVideo");
        File mp4File = new File(mp4Folder + "\\" + videoName + ".mp4");
        ArrayList<String> fileNames = new ArrayList<>(java.util.List.of(Objects.requireNonNull(screenshotsFolder.list())));
        ArrayList<File> fileList = new ArrayList<>();
        int numScreenshots = fileNames.size();

        quickSort(fileNames, 0, fileNames.size() - 1);

        String path;
        try {
            for (String s : fileNames) {
                path = "C:\\RecorderProgram\\Screenshots\\" + s;
                screenshotsFolder = new File(path);
                fileList.add(screenshotsFolder);
            }
        } catch (NullPointerException nullPointerException) {
            System.out.println("The folder containing images is empty.");
            nullPointerException.printStackTrace();
        }

        int fps = numScreenshots / seconds;
        AWTSequenceEncoder sequenceEncoder = AWTSequenceEncoder.createSequenceEncoder(mp4File, fps/2);
        BufferedImage image;
        File screenshotsFile;
        int loop = 0;

        try {
            for (File screenshot : fileList) {
                path = screenshot.getPath();
                screenshotsFile = new File(path);
                image = ImageIO.read(screenshotsFile);
                sequenceEncoder.encodeImage(image);
                loop++;
                if(loop == 250){
                    System.out.println("250");
                }
                screenshot.delete();

            }

            sequenceEncoder.finish();
            System.out.println("finished encoding");
        } catch (Exception e) {
            sequenceEncoder.finish();
            e.printStackTrace();
        }
    }

    private static void executeScreenCap(int endYear, int endMonth, int endDay, int ending_hour, int ending_minute, int i, int screenHeight, int screenWidth) throws IOException {

        //todo: Make sure everything is passing and check PATH natively https://stackoverflow.com/questions/318239/how-do-i-set-environment-variables-from-java
        Runtime.getRuntime().exec("cmd /c start cmd.exe /K testPub\\recordingapp1.exe " + endYear + ","
                + endMonth + "," + endDay + ","+ ending_hour + ","+ ending_minute + ","+ i + "," +
                screenHeight + "," + screenWidth);
    }

    public static void combineAudioWithVideo(String fileName, String outputName) {
        try {
            Runtime.getRuntime().exec("cmd /c start cmd.exe /K \"ffmpeg -i " +
                    "C:\\RecorderProgram\\SoundlessVideo\\" + fileName + "_soundless.mp4 -i " +
                    "C:\\RecorderProgram\\Audio\\" + fileName + ".wav " + "-shortest C:\\RecorderProgram\\FinalVideo\\\"" + outputName);
            //Runtime.getRuntime().exec("ffmpeg -i C:\\RecorderProgram\\FirstVideo\\video.mp4 -i C:\\RecorderProgram\\Audio\\audio.wav -shortest C:\\RecorderProgram\\" + outputName);

        } catch (Exception e) {
            System.out.println("Unable to combine audio and video");
            e.printStackTrace();
        }
    }

    public static void After_Login(String match_ID) throws IOException, URISyntaxException, AWTException, SQLException, InterruptedException {
        ArrayList<Meeting> meetings_from_DB = Gather_User_Meetings_From_DB(match_ID);

        //uncomment to skip login for testing
        //ArrayList<Meeting> meetings_from_DB = Gather_User_Meetings_From_DB(String.valueOf(1));

        ArrayList<Meeting> meeting_object_list = new ArrayList<>();

        String meetingName;
        String meetingID;
        String meetingPassword;
        int starting_hour;
        int starting_minute;
        int starting_am_pm;
        int ending_hour;
        int ending_minute;
        int ending_am_pm;

        for (Meeting gathered_meeting : meetings_from_DB) {
            meetingName = gathered_meeting.getMeetingName();
            meetingID = gathered_meeting.getMeetingID();
            meetingPassword = gathered_meeting.getMeetingPassword();

            starting_hour = gathered_meeting.getStarting_hour();
            starting_minute = gathered_meeting.getStarting_minute();
            starting_am_pm = gathered_meeting.getStarting_am_pm();

            ending_hour = gathered_meeting.getEnding_hour();
            ending_minute = gathered_meeting.getEnding_minute();
            ending_am_pm = gathered_meeting.getEnding_am_pm();

            Meeting meeting_object = new Meeting(meetingName, meetingID, meetingPassword, starting_hour, starting_minute, starting_am_pm,
                    ending_hour, ending_minute, ending_am_pm);
            meeting_object_list.add(meeting_object);
        }

        Meeting selected_meeting = priorMeetingSelector(meeting_object_list, match_ID);

        String meeting_name = selected_meeting.getMeetingName();
        meetingID = selected_meeting.getMeetingID();
        meetingPassword = selected_meeting.getMeetingPassword();
        starting_hour = selected_meeting.getStarting_hour();
        starting_minute = selected_meeting.getStarting_minute();
        ending_hour = selected_meeting.getEnding_hour();
        ending_minute = selected_meeting.getEnding_minute();

        LocalTime meeting_start_time = LocalTime.of(starting_hour, starting_minute, 0);
        int login_minute = starting_minute - 1;
        int login_hour = starting_hour;
        if (login_minute == -1) {
            login_minute = 59;
            login_hour = starting_hour - 1;
            if (login_hour == -1) {
                login_hour = 23;
            }
        }

        LocalTime login_time = LocalTime.of(login_hour, login_minute, 0);
        LocalTime currentTime = LocalTime.now();
        LocalTime meeting_end_time = LocalTime.of(ending_hour, ending_minute, 0);

        String originalOutputName = (LocalDate.now() + meeting_name).replaceAll(" ", "_");
        long startNano = meeting_start_time.toNanoOfDay();
        long endNano = meeting_end_time.toNanoOfDay();
        long totalNano = endNano - startNano;

        int endYear = LocalDate.now().getYear();
        int endMonth = LocalDate.now().getMonthValue();
        int endDay = LocalDate.now().getDayOfMonth();

        Robot robot = new Robot();
        while (currentTime.isBefore(meeting_start_time) | currentTime.isAfter(meeting_end_time)) {
            currentTime = LocalTime.now();
            //System.out.println(currentTime);
            robot.delay(500);
            if (currentTime.isBefore(login_time) | currentTime.isAfter(meeting_end_time)) {
                //System.out.println("Not starting Yet");
                JDialog standby = new JDialog();
                standby.addWindowListener(null);
                standby.setTitle("Waiting for start time");
                standby.setDefaultCloseOperation(2);
                Timer timer = new Timer(10000, (e) -> {
                    standby.setVisible(false);
                    standby.dispose();
                });
                timer.start();
                standby.setVisible(true);
                robot.delay(10000);
                standby.dispose();
            } else {
                System.out.println("starting");
                Runtime runtime = Runtime.getRuntime();


                try {
                    runtime.exec("C:\\Program Files (x86)\\Zoom\\bin\\Zoom.exe");
                    robot.delay(4000);
                } catch (IOException ioException) {
                    Error_Box("Failed to open Zoom", "Opening Operation Failed");
                    ioException.printStackTrace();
                    break;
                }

                robot.keyPress(10);
                robot.keyRelease(10);
                robot.delay(5000);

                for (int idCharInt = 0; idCharInt < meetingID.length(); ++idCharInt) {
                    robot.keyPress(meetingID.charAt(idCharInt));
                    robot.keyRelease(meetingID.charAt(idCharInt));
                    System.out.println(meetingID.charAt(idCharInt));
                }

                robot.delay(1000);
                robot.keyPress(10);
                robot.keyRelease(10);
                robot.delay(3000);
                if (meetingPassword == null) {
                    meetingPassword = "";
                }

                StringSelection passCopy = new StringSelection(meetingPassword);
                Clipboard passClipboard = Toolkit.getDefaultToolkit().getSystemClipboard();
                passClipboard.setContents(passCopy, passCopy);
                //System.out.println("Password has been pasted");
                robot.keyPress(17);
                robot.keyPress(86);
                robot.keyRelease(86);
                robot.keyRelease(17);
                robot.delay(3000);
                robot.keyPress(10);
                robot.keyRelease(10);
                robot.delay(3000);

/*
                //sets a character to each thread so screenshots from each will be unique
                char character = 'a';
                Video_Class screenshotTaker1 = new Video_Class(meeting_end_time);
                character = (char) (character + 1);
                Video_Class screenshotTaker2 = new Video_Class(meeting_end_time);
                ++character;
                Video_Class screenshotTaker3 = new Video_Class(meeting_end_time);
                ++character;
                Video_Class screenshotTaker4 = new Video_Class(meeting_end_time);
                ++character;
                Video_Class screenshotTaker5 = new Video_Class(meeting_end_time);
*/

                Rectangle screenSize = new Rectangle(Toolkit.getDefaultToolkit().getScreenSize());
                int screenHeight = screenSize.height;
                int screenWidth = screenSize.width;
                executeScreenCap(endYear,endMonth,endDay,ending_hour,ending_minute, 0, screenHeight, screenWidth);
                //Process executeScreenCapture = Runtime.getRuntime().exec("cmd /c start cmd.exe /K testPub\\recordingapp1.exe 2021,9,9,2,15,0,0,0");
                while (currentTime.isBefore(meeting_end_time)){
                    Thread.sleep(60000);
                    System.out.println("waiting");
                    currentTime = LocalTime.now();
                }

                final long RECORD_TIME = (meeting_end_time.toNanoOfDay() - meeting_start_time.toNanoOfDay()) / 1000000;
/*
                SoundRecorder recorder = new SoundRecorder(originalOutputName, meeting_end_time);

                Thread t6 = new Thread(recorder);

                t6.start();
                System.out.println("audio up");*/
                /*t1.start();
                System.out.println("t1 up");
                t2.start();
                //System.out.println("t2 up");
                t3.start();
                //System.out.println("t3 up");
                t4.start();
                //System.out.println("t4 up");
                t5.start();
                System.out.println("t5 up");

                //verifies the screenshots have finished before moving on
                t5.join();*/
                //recorder.finish();

                //System.out.println("t5 joined");

                System.out.println("Creating MP4");
                createMP4(originalOutputName + "_soundless", (int) (totalNano / 1000000000));

                String finalOutputName = (meeting_name + LocalDate.now() + ".mp4").replaceAll(" ", "_");

                System.out.println("Combining Video And Audio");
                combineAudioWithVideo(originalOutputName, finalOutputName);

                System.out.println("Done :D");
                System.exit(0);
            }
        }
    }

    public static void main(String[] args) throws AWTException, IOException, URISyntaxException, InterruptedException, LineUnavailableException, SQLException, NoSuchAlgorithmException, InvalidKeySpecException {
/*
        LocalTime meeting_end_time = LocalTime.of(16,42,0);
        LocalTime currentTime = LocalTime.now();
        Thread recordingSleep = new Thread();
        //executeScreenCap(2021,9,15,16,35,0,2180,1920);
        recordingSleep.start();
        //Process executeScreenCapture = Runtime.getRuntime().exec("cmd /c start cmd.exe /K testPub\\recordingapp1.exe 2021,9,9,2,15,0,0,0");
        while (currentTime.isBefore(meeting_end_time)){
            Thread.sleep(60000);
            System.out.println("waiting");
            currentTime = LocalTime.now();
        }
        System.out.println("done");
        System.exit(0);*/
        fileVerify();
        User_Login();

    }
}