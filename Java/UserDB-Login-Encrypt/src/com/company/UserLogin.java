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


public class UserLogin extends JDialog {
    private int idNumber;
    private final JTextField usernameTextfield;
    private final JPasswordField passwordField;
    private boolean loginSuccess = false;

    //private final Connection connection = DriverManager.getConnection("jdbc:sqlite:src/identifier.sqlite");

    //Accesses the database and gathers all the usernames, hashed passwords, and emails as well as the user ID #
    private static ArrayList<ArrayList> gatherLoginsFromDatabase() {
        String jdbcURL = "jdbc:sqlite:src/identifier.sqlite";

        ArrayList<ArrayList> userObjectList = new ArrayList<>();
        try {
            Connection connection = DriverManager.getConnection(jdbcURL);
            Statement getUsernameStatement = connection.createStatement();
            Statement getPasswordStatement = connection.createStatement();
            Statement getEmailStatement = connection.createStatement();
            ResultSet usernameSet = getUsernameStatement.executeQuery("SELECT * FROM Usernames");
            ResultSet passwordSet = getPasswordStatement.executeQuery("SELECT * FROM Passwords");
            ResultSet emailSet = getEmailStatement.executeQuery("SELECT * FROM EMAIL");
            while (usernameSet.next() && passwordSet.next() && emailSet.next()) {
                ArrayList<String> userObject = new ArrayList<>();
                String uns = usernameSet.getString(1);
                if(usernameSet.getString(1) != null) {

                    String dbUsername = usernameSet.getString(2);
                    String dbPassword = passwordSet.getString(2);
                    String dbEmail = emailSet.getString(2);

                    userObject.add(dbUsername);
                    userObject.add(dbPassword);
                    userObject.add(dbEmail);

                    userObjectList.add(userObject);

                }
            }
            connection.close();
        }
        catch (SQLException throwables) {
            System.out.println("Unable to connect to the database");

            throwables.printStackTrace();
        }
        return userObjectList;
    }

    //creates the UI for a user to log in and checks the entered information against already existing users loaded from
    //the database
    public UserLogin(Frame parent) throws SQLException {
        super(parent, "Login", true);
        ArrayList<ArrayList> loadedUserDatabase = gatherLoginsFromDatabase();
        //loadedUserDatabase.remove(0);

        JPanel panel = new JPanel(new GridBagLayout());
        GridBagConstraints gridBagConstraint = new GridBagConstraints();

        gridBagConstraint.fill = GridBagConstraints.HORIZONTAL;

        JLabel usernameLabel = new JLabel("Username: ");
        gridBagConstraint.gridx = 0;
        gridBagConstraint.gridy = 0;
        gridBagConstraint.gridwidth = 1;
        panel.add(usernameLabel, gridBagConstraint);

        usernameTextfield = new JTextField(20);
        gridBagConstraint.gridx = 1;
        gridBagConstraint.gridy = 0;
        gridBagConstraint.gridwidth = 2;
        panel.add(usernameTextfield, gridBagConstraint);

        JLabel passwordLabel = new JLabel("Password: ");
        gridBagConstraint.gridx = 0;
        gridBagConstraint.gridy = 1;
        gridBagConstraint.gridwidth = 1;
        panel.add(passwordLabel, gridBagConstraint);

        passwordField = new JPasswordField(20);
        gridBagConstraint.gridx = 1;
        gridBagConstraint.gridy = 1;
        gridBagConstraint.gridwidth = 2;
        panel.add(passwordField, gridBagConstraint);
        panel.setBorder(new LineBorder(Color.GRAY));


        JButton loginButton = new JButton("Login");
        JButton newUserButton = new JButton("New Account");
        JButton cancelButton = new JButton("Cancel");

        JPanel bp = new JPanel();
        bp.add(loginButton);
        bp.add(cancelButton);
        bp.add(newUserButton);

        getContentPane().add(panel, BorderLayout.CENTER);
        getContentPane().add(bp, BorderLayout.PAGE_END);
        //frame.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);

        pack();
        setResizable(false);
        setLocationRelativeTo(parent);

        loginButton.addActionListener(e -> {
            try {
                //passes the entered password into the password security class via authenticate() to compare against the hashed password
                if (authenticate(getUsername(), getPassword(), loadedUserDatabase)) {
                    loginSuccess = true;
                    dispose();
                } else {
                    JOptionPane.showMessageDialog(UserLogin.this,
                            "Invalid username or password",
                            "Login",
                            JOptionPane.ERROR_MESSAGE);
                    // reset username and password
                    usernameTextfield.setText("");
                    passwordField.setText("");
                    loginSuccess = false;

                }
            } catch (NoSuchAlgorithmException | InvalidKeySpecException ex) {
                ex.printStackTrace();
            }
        });

        cancelButton.addActionListener(new ActionListener() {

            public void actionPerformed(ActionEvent e) {
                dispose();
                System.exit(0);
            }
        });

        //starts new user creation process
        newUserButton.addActionListener(new ActionListener() {

            public void actionPerformed(ActionEvent e) {
                try {
                    dispose();
                    createUser();
                } catch (SQLException | NoSuchAlgorithmException | InvalidKeySpecException ex) {
                    ex.printStackTrace();
                }
                dispose();
            }
        });
    }

    //creates a new user and adds them to the database
    public User createUser() throws SQLException, NoSuchAlgorithmException, InvalidKeySpecException {
        PasswordSecurity ps = new PasswordSecurity();
        User newUser = new User();
        newUser.setUsername(String.valueOf(JOptionPane.showInputDialog("Enter a username")));
        newUser.setPassword(String.valueOf(JOptionPane.showInputDialog("Enter a password")));
        newUser.setEmail(String.valueOf(JOptionPane.showInputDialog("Enter an email")));

        addToDatabase(newUser);
        dispose();
        return newUser;
    }

    private int addToDatabase(User newUser) throws SQLException {
        int numRowsInserted = 0;
        PreparedStatement preparedStatement = null;
        String usernameInsert =
                "INSERT INTO Usernames(username) VALUES(?)";
        String passwordInsert =
                "INSERT INTO Passwords(password) VALUES(?)";
        String emailInsert =
                "INSERT INTO EMAIL(email) VALUES(?)";
        try {
            String jdbcURL = "jdbc:sqlite:src/identifier.sqlite";
            Connection connection = DriverManager.getConnection(jdbcURL);
            preparedStatement = connection.prepareStatement(usernameInsert);
            preparedStatement.setString(1, newUser.getUsername());
            numRowsInserted = preparedStatement.executeUpdate();

            preparedStatement = connection.prepareStatement(passwordInsert);
            preparedStatement.setString(1, newUser.getPassword());
            numRowsInserted = preparedStatement.executeUpdate();

            preparedStatement = connection.prepareStatement(emailInsert);
            preparedStatement.setString(1, newUser.getEmail());
            numRowsInserted = preparedStatement.executeUpdate();
            connection.close();

            //numRowsInserted = preparedStatement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        }
        System.out.println(numRowsInserted + "Rows inserted, added to DB");
        return numRowsInserted;
    }


    public String getUsername() {
        return usernameTextfield.getText().trim();
    }

    public String getPassword() {
        return new String(passwordField.getPassword());
    }

    public int getIdNumber() {
        return this.idNumber;
    }

    public boolean loginSuccessful() {
        return loginSuccess;
    }

    //creates a user object from the data obtained from the database and compares it to what the user input is.
    //creates instance of the passsword security class to verify that the password entered with the corresponding username
    // is correct in comparison with the hash.
    private boolean authenticate(String username, String password, ArrayList<ArrayList> loadedUserDatabase) throws NoSuchAlgorithmException, InvalidKeySpecException {
        PasswordSecurity passwordSecurity = new PasswordSecurity();
        ArrayList userObject;

        for (int i = 0; i < loadedUserDatabase.size(); i++) {
            userObject = loadedUserDatabase.get(i);
            String dbUsername = (String) userObject.get(0);
            String dbPassword = (String) userObject.get(1);
            boolean passwordCheck = passwordSecurity.checkPassword(password, dbPassword);
            if (username.equalsIgnoreCase(dbUsername) && passwordCheck) {
                this.idNumber = Integer.parseInt((String) userObject.get(2));
                JOptionPane.showMessageDialog(null, "Login Successful");
                return true;
            }
        }
        return false;
    }
}
