package com.company;

import javax.swing.*;
import javax.swing.border.LineBorder;
import java.awt.*;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.security.NoSuchAlgorithmException;
import java.security.spec.InvalidKeySpecException;
import java.sql.*;
import java.util.ArrayList;

//public class User_Login extends JFrame implements ActionListener {

public class User_Login extends JDialog {
    private String username;
    private String password;
    private String match_ID;
    private JTextField username_textfield;
    private JPasswordField password_field;
    private JLabel username_label;
    private JLabel password_label;
    private JButton login_button;
    private JButton cancel_button;
    private boolean login_Sucess = false;

    private static ArrayList<String[]> Gather_Logins_From_DB() {
        String jdbcURL = "jdbc:sqlite:src/usersdb.db";

        ArrayList<String[]> user_object_list = new ArrayList<>();
        try {
            Connection connection = DriverManager.getConnection(jdbcURL);
            String user_table = "SELECT * FROM users";
            Statement statement = connection.createStatement();
            ResultSet user_table_result = statement.executeQuery(user_table);
            while (user_table_result.next()) {
                String[] user_object = new String[3];
                String DB_username = user_table_result.getString(1);
                String DB_password = user_table_result.getString(2);
                String DB_matchID = user_table_result.getString(3);
                user_object[0] = DB_username;
                user_object[1] = DB_password;
                user_object[2] = DB_matchID;
                user_object_list.add(user_object);
            }
        }
        catch (SQLException throwables) {
            System.out.println("Unable to connect to the database");
            throwables.printStackTrace();
        }
        return user_object_list;
    }

    public User_Login(Frame parent) {
        super(parent, "Login", true);
        ArrayList<String[]> loaded_user_DB = Gather_Logins_From_DB();

        //
        JPanel panel = new JPanel(new GridBagLayout());
        GridBagConstraints grid_bag_constraint = new GridBagConstraints();

        grid_bag_constraint.fill = GridBagConstraints.HORIZONTAL;

        username_label = new JLabel("Username: ");
        grid_bag_constraint.gridx = 0;
        grid_bag_constraint.gridy = 0;
        grid_bag_constraint.gridwidth = 1;
        panel.add(username_label, grid_bag_constraint);

        username_textfield = new JTextField(20);
        grid_bag_constraint.gridx = 1;
        grid_bag_constraint.gridy = 0;
        grid_bag_constraint.gridwidth = 2;
        panel.add(username_textfield, grid_bag_constraint);

        password_label = new JLabel("Password: ");
        grid_bag_constraint.gridx = 0;
        grid_bag_constraint.gridy = 1;
        grid_bag_constraint.gridwidth = 1;
        panel.add(password_label, grid_bag_constraint);

        password_field = new JPasswordField(20);
        grid_bag_constraint.gridx = 1;
        grid_bag_constraint.gridy = 1;
        grid_bag_constraint.gridwidth = 2;
        panel.add(password_field, grid_bag_constraint);
        panel.setBorder(new LineBorder(Color.GRAY));

        login_button = new JButton("Login");

        login_button.addActionListener(e -> {
            try {
                if (authenticate(getUsername(), getPassword(), loaded_user_DB)) {
                    login_Sucess = true;
                    dispose();
                } else {
                    JOptionPane.showMessageDialog(User_Login.this,
                            "Invalid username or password",
                            "Login",
                            JOptionPane.ERROR_MESSAGE);
                    // reset username and password
                    username_textfield.setText("");
                    password_field.setText("");
                    login_Sucess = false;

                }
            } catch (NoSuchAlgorithmException | InvalidKeySpecException ex) {
                ex.printStackTrace();
            }
        });
        cancel_button = new JButton("Cancel");
        cancel_button.addActionListener(new ActionListener() {

            public void actionPerformed(ActionEvent e) {
                dispose();
                System.exit(0);
            }
        });
        JPanel bp = new JPanel();
        bp.add(login_button);
        bp.add(cancel_button);

        getContentPane().add(panel, BorderLayout.CENTER);
        getContentPane().add(bp, BorderLayout.PAGE_END);

        pack();
        setResizable(false);
        setLocationRelativeTo(parent);
    }

    public String getUsername() {
        return username_textfield.getText().trim();
    }

    public String getPassword() {
        return new String(password_field.getPassword());
    }
    public String getMatchID() {
        return this.match_ID;
    }

    public boolean Login_Successful() {
        return login_Sucess;
    }

    private boolean authenticate(String username, String password, ArrayList<String[]> loaded_user_DB) throws NoSuchAlgorithmException, InvalidKeySpecException {
        PasswordSecurity passwordSecurity = new PasswordSecurity();
        String[] user_object;
        for (int i = 0; i < loaded_user_DB.size(); i++) {
            user_object = loaded_user_DB.get(i);
            String dbUsername = user_object[0];
            String dbPassword = user_object[1];
            boolean passwordCheck = passwordSecurity.checkPassword(password, dbPassword);
            if (username.equalsIgnoreCase(dbUsername) && passwordCheck) {
                this.username = user_object[0];
                this.password = user_object[1];
                this.match_ID = user_object[2];
                JOptionPane.showMessageDialog(null, "Login Successful");
                return true;
            }
        }
        return false;
    }
}
