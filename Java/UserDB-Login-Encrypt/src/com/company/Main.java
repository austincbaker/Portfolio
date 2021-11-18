package com.company;

import javax.swing.*;
import java.awt.*;
import java.sql.*;

public class Main {

    // Password for Austin is Password1*
    // Password for test is TestPassword1*
    public static synchronized void User_Login() {
        final JFrame frame = new JFrame("User Login");
        JButton login_button = new JButton("Click to login");
        frame.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);
        frame.setSize(300, 100);
        frame.setLayout(new FlowLayout());
        frame.getContentPane().add(login_button);
        frame.setVisible(true);
        login_button.addActionListener(e -> {
            frame.dispose();
            boolean move_on = false;
            UserLogin userLogin = null;
            try {
                userLogin = new UserLogin(frame);
            } catch (SQLException ex) {
                ex.printStackTrace();
            }
            userLogin.setVisible(true);

            while (!move_on) {
                if (userLogin.loginSuccessful()) {
                    //String username = userLogin.getUsername();
                    //String password = userLogin.getPassword();
                    int match_ID = userLogin.getIdNumber();
                    frame.dispose();

                    try {
                        //After_Login(match_ID);
                    } catch (Exception ioException) {
                        ioException.printStackTrace();
                        move_on = true;
                    }
                }
            }

        });
    }

    public static void main(String[] args){
        User_Login();
    }
}
