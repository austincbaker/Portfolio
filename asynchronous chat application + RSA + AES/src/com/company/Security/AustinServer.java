package com.company;

import javax.crypto.*;
import javax.crypto.spec.PBEKeySpec;
import javax.crypto.spec.SecretKeySpec;
import java.io.*;
import java.math.BigInteger;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketException;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.spec.InvalidKeySpecException;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.*;

public class AustinServer {

    // Vector to store active clients
    public static Vector<ClientList> clientListVector = new Vector<>();
    static String password = "Password1234#";
    ServerAes serverAes = new ServerAes();

    // counter for clients
    static int i = 0;

    public static void main(String[] args) throws IOException, NoSuchAlgorithmException, IllegalBlockSizeException, NoSuchPaddingException, BadPaddingException, InvalidKeyException {
        System.out.println("Thank you for starting the application. This chat application implements client to client messaging" +
                "which is encrypted using RSA and AES encryption. It has group and private chat functions as well. The application" +
                "also saves the chat history in the same files as you keys. To remove those files, please see C:/413ChatApp/");
        ServerSocket serverSocket = new ServerSocket(57392);
        Socket socket;
        ServerRsaU rsaU = new ServerRsaU();
        ServerAes serverAes = new ServerAes();
        ServerPass ps = new ServerPass();
        //password = ps.createStrongRandomPassword();
        //password = "Password1234#";
        // running infinite loop for getting
        // client request
        while (true)
        {
            // Accept the incoming request
            socket = serverSocket.accept();
            // obtain input and output streams
            DataInputStream dis = new DataInputStream(socket.getInputStream());
            DataOutputStream dos = new DataOutputStream(socket.getOutputStream());
            System.out.println("New client request received : " + socket + "\n");

            String receivedKey = dis.readUTF();

            //encrypt the password in RSA using the clients public key
            System.out.println("Password is: " + password + "\n");
            String encryptedPassword = Base64.getEncoder().encodeToString(rsaU.encrypt(password, receivedKey));
            System.out.println("Encrypted Password:: "+ encryptedPassword + "\n");
            dos.writeUTF(encryptedPassword);

            //obtain confirmation the client received the password
            String confirmPasswordRecipt= "blank";
            while(!confirmPasswordRecipt.equalsIgnoreCase("Received")){
                confirmPasswordRecipt = serverAes.decrypt(dis.readUTF(),password);
                System.out.println(confirmPasswordRecipt);
            }
            String welcomeMsg = """
                    Please format the message in Your Message @Recipient Name
                     To send a message in the general chat, use @All Message
                    """;
            //System.out.println("Confirmation received");
            //String encryptWelcome = serverAes.encrypt(welcomeMsg,password);
            //dos.writeUTF(encryptWelcome);

            dos.writeUTF(serverAes.encrypt(welcomeMsg, password));
            System.out.println("welcome sent");
            //dos.writeUTF("Start Threads" + "\n");
            //dos.writeUTF(serverAes.encrypt("Enter your Name: ",password));

            dos.writeUTF(serverAes.encrypt("Enter your Name: ", password));
            String name = serverAes.decrypt(dis.readUTF(), password);

            // Create a new handler object for handling this request.
            ClientList newClient = new ClientList(socket,name, dis, dos, password, serverAes);

            // Create a new Thread with this object.
            Thread t = new Thread(newClient);

            System.out.printf("Adding %s to active client list%n", name + "\n");

            // add this client to active clients list
            clientListVector.add(newClient);

            // start the thread.
            t.start();
        }
    }
}

// ClientList class
class ClientList implements Runnable {
    ServerAes serverAes = new ServerAes();
    Scanner scanner = new Scanner(System.in);
    protected String name;
    DataInputStream dataInputStream;
    DataOutputStream dataOutputStream;
    Socket socket;
    boolean isloggedin;
    String password;
    ServerAes aes;

    // constructor
    public ClientList(Socket socket, String name,
                      DataInputStream dataInputStream, DataOutputStream dataOutputStream, String password, ServerAes aes) {
        this.dataInputStream = dataInputStream;
        this.dataOutputStream = dataOutputStream;
        this.name = name;
        this.socket = socket;
        this.isloggedin = true;
        this.password = password;
        this.aes = aes;
    }

    @Override
    public void run() {
        String fromClient;
        //String key = aes.setKey(password);
        while (true) {
            try {
                fromClient = dataInputStream.readUTF();
                //new String(fromClient, "UTF-8");
                //System.out.println(fromClient.toString());
                if (fromClient.length() > 0) {
                    System.out.println("Received Message");
                    // receive the string
                    String decryptedMsg = aes.decrypt(fromClient, password);
                    if (decryptedMsg == null) {
                        System.out.println("Decrypted msg null \n");
                        return;
                    }
                    //System.out.println(decryptedMsg);
                    //System.out.println("Decrypted Message");
                    if (fromClient.equals("bye")) {
                        this.isloggedin = false;
                        this.socket.close();
                        break;
                    }
                    // break the string into message and recipient part
                    StringTokenizer stringTokenizer = new StringTokenizer(decryptedMsg, "@");
                    String messageSending = stringTokenizer.nextToken().trim();
                    String recipient = stringTokenizer.nextToken().trim();
                    //System.out.println("Recipient: " + recipient + "\n");
                    //System.out.println("MessageSending: " + messageSending + "\n");


                    // search for the recipient in the connected devices list.
                    // clientListVector is the vector storing client of active users
                    for (ClientList mc : AustinServer.clientListVector) {
                        String lookingFor = mc.name;
                        //System.out.println("Name to match: " + recipient);
                        // if the recipient is found, write on its
                        // output stream
                        if (recipient.equalsIgnoreCase(lookingFor)) {
                            mc.dataOutputStream.writeUTF(serverAes.encrypt((this.name + " :@ " + fromClient),password));
                            dataOutputStream.flush();
                        }
                    }
                    if (recipient.equalsIgnoreCase("all")) {
                        //System.out.println("Writing to all");
                        for (ClientList mc2 : AustinServer.clientListVector) {
                            if (!this.name.equalsIgnoreCase(mc2.name)) {
                                //System.out.println(this.name + " equals " + mc2.name + "\n");
                                //System.out.println(mc2.name + "Got the message");
                                mc2.dataOutputStream.writeUTF(serverAes.encrypt((this.name + " :@ " + fromClient),password));
                                dataOutputStream.flush();
                            }
                        }
                    }
               // }
                }/*
                else {
                    return;
                }*/
            } catch (SocketException sc){
                try {for(ClientList ch : AustinServer.clientListVector){
                    if(this.name.equalsIgnoreCase(ch.name)){
                        break;
                    }
                    ch.dataOutputStream.writeUTF(this.name + "Left the chat");
                }
                    this.dataInputStream.close();
                    this.dataOutputStream.close();
                    socket.close();

                } catch (IOException e) {
                    e.printStackTrace();
                }

            }
            catch(NoSuchElementException nse){
                try {
                    dataOutputStream.writeUTF(serverAes.encrypt("Unable to send. Please format the message in 'Recipient name' $ Message", password));
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }

            catch (IOException e) {

                e.printStackTrace();
            }
        }
    }
}

class ServerRsaU {

    private static String publicKey = "";
    private static String privateKey = "";

    public static PublicKey getPublicKey(String base64PublicKey){
        PublicKey publicKey = null;
        try{
            X509EncodedKeySpec keySpec = new X509EncodedKeySpec(Base64.getDecoder().decode(base64PublicKey.getBytes()));
            KeyFactory keyFactory = KeyFactory.getInstance("RSA");
            publicKey = keyFactory.generatePublic(keySpec);
            return publicKey;
        } catch (NoSuchAlgorithmException e) {
            e.printStackTrace();
        } catch (InvalidKeySpecException e) {
            e.printStackTrace();
        }
        return publicKey;
    }

    public static PrivateKey getPrivateKey(String base64PrivateKey){
        PrivateKey privateKey = null;
        PKCS8EncodedKeySpec keySpec = new PKCS8EncodedKeySpec(Base64.getDecoder().decode(base64PrivateKey.getBytes()));
        KeyFactory keyFactory = null;
        try {
            keyFactory = KeyFactory.getInstance("RSA");
        } catch (NoSuchAlgorithmException e) {
            e.printStackTrace();
        }
        try {
            privateKey = keyFactory.generatePrivate(keySpec);
        } catch (InvalidKeySpecException e) {
            e.printStackTrace();
        }
        return privateKey;
    }

    public byte[] encrypt(String data, String publicKey) throws BadPaddingException, IllegalBlockSizeException, InvalidKeyException, NoSuchPaddingException, NoSuchAlgorithmException {
        Cipher cipher = Cipher.getInstance("RSA/ECB/PKCS1Padding");
        cipher.init(Cipher.ENCRYPT_MODE, getPublicKey(publicKey));
        return cipher.doFinal(data.getBytes());
    }

    public static String decrypt(byte[] data, PrivateKey privateKey) throws NoSuchPaddingException, NoSuchAlgorithmException, InvalidKeyException, BadPaddingException, IllegalBlockSizeException {
        Cipher cipher = Cipher.getInstance("RSA/ECB/PKCS1Padding");
        cipher.init(Cipher.DECRYPT_MODE, privateKey);
        return new String(cipher.doFinal(data));
    }

    public static String decrypt(String data, String base64PrivateKey) throws IllegalBlockSizeException, InvalidKeyException, BadPaddingException, NoSuchAlgorithmException, NoSuchPaddingException {
        return decrypt(Base64.getDecoder().decode(data.getBytes()), getPrivateKey(base64PrivateKey));
    }

    /*public static void main(String[] args) throws IllegalBlockSizeException, InvalidKeyException, NoSuchPaddingException, BadPaddingException {
        try {
            String encryptedString = Base64.getEncoder().encodeToString(encrypt("Test", publicKey));
            System.out.println(encryptedString);
            String decryptedString = decrypt(encryptedString, privateKey);
            System.out.println(decryptedString);
        } catch (NoSuchAlgorithmException e) {
            System.err.println(e.getMessage());
        }

    }*/
}
class ServerPass {

    //gives the option to have a strong password created  for the user completely randomly.

    public String createStrongRandomPassword() throws NoSuchAlgorithmException, InvalidKeySpecException {
        char[] charsList = " 1234567890.-_?$*)(#%/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ".toCharArray();
        ArrayList<Character> numsAndSpecs = new ArrayList<>();

        for (int i = 1; i < charsList.length; i++) {
            numsAndSpecs.add(charsList[i]);
        }
        StringBuilder password = new StringBuilder();
        for (int i = 0; i < 16; i++) {
            Random random = new Random();
            char passChar = charsList[random.nextInt(charsList.length)];
            password.append(passChar);
        }
        char[] fullPass = password.toString().toCharArray();
        int specCharCheck = 0;

        //verify that there are at least three numbers or special characters in the password.
        for (var c : fullPass) {
            if (numsAndSpecs.contains(c)) {
                specCharCheck++;
                if (specCharCheck == 3) {
                    break;
                }
            }
        }
        //if there are not three numbers or characters, runs recursively until there are.
        if (specCharCheck != 3) {
            return createStrongRandomPassword();
        }

        //todo: Implement a way to send the password to the user, probably by email?

        return password.toString();

        //return createPasswordHash(password.toString());
    }

    public static String createPasswordHash(String password) throws NoSuchAlgorithmException, InvalidKeySpecException {
        int iterations = 1000;
        char[] charsArray = password.toCharArray();
        byte[] saltArray = getSalt();

        PBEKeySpec spec = new PBEKeySpec(charsArray, saltArray, iterations, 64 * 8);
        SecretKeyFactory skf = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA1");
        byte[] hashArray = skf.generateSecret(spec).getEncoded();
        return iterations + ":" + toHex(saltArray) + ":" + toHex(hashArray);
    }

    private static byte[] getSalt() throws NoSuchAlgorithmException {
        SecureRandom sr = SecureRandom.getInstance("SHA1PRNG");
        byte[] saltArray = new byte[16];
        sr.nextBytes(saltArray);
        return saltArray;
    }

    private static String toHex(byte[] array) throws NoSuchAlgorithmException {
        BigInteger bi = new BigInteger(1, array);
        String hex = bi.toString(16);
        int paddingLength = (array.length * 2) - hex.length();
        if (paddingLength > 0) {
            return String.format("%0" + paddingLength + "d", 0) + hex;
        } else {
            return hex;
        }
    }

    public boolean checkPassword(String enteredPassword, String storedPassword) throws NoSuchAlgorithmException, InvalidKeySpecException {
        String[] parts = storedPassword.split(":");
        int iterations = Integer.parseInt(parts[0]);
        byte[] saltArray = fromHex(parts[1]);
        byte[] hashArray = fromHex(parts[2]);

        PBEKeySpec spec = new PBEKeySpec(enteredPassword.toCharArray(), saltArray, iterations, hashArray.length * 8);
        SecretKeyFactory skf = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA1");
        byte[] testHash = skf.generateSecret(spec).getEncoded();

        int diff = hashArray.length ^ testHash.length;
        for (int i = 0; i < hashArray.length && i < testHash.length; i++) {
            diff |= hashArray[i] ^ testHash[i];
        }
        return diff == 0;
    }

    private static byte[] fromHex(String hex) throws NoSuchAlgorithmException {
        byte[] byteList = new byte[hex.length() / 2];
        for (int i = 0; i < byteList.length; i++) {
            byteList[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return byteList;
    }
}
class ServerAes {

    private SecretKeySpec secretKeySpec;
    private byte[] key;

    public String setKey(String myKey) {
        try {
            key = myKey.getBytes(StandardCharsets.UTF_8);
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            key = sha.digest(key);
            key = Arrays.copyOf(key, 16);
            secretKeySpec = new SecretKeySpec(key, "AES");
            return String.valueOf(secretKeySpec);
        } catch (NoSuchAlgorithmException e) {
            e.printStackTrace();
        }
        return myKey;
    }

    public String encrypt(String unencryptedString, String secretString) {
        try {
            setKey(secretString);
            Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
            cipher.init(Cipher.ENCRYPT_MODE, secretKeySpec);
            return Base64.getEncoder().encodeToString(cipher.doFinal(unencryptedString.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            System.out.println("Error while encrypting: " + e);
            return secretString;
        }
    }

    public String decrypt(String encryptedString, String secretString) {
        try {
            setKey(secretString);
            Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5PADDING");
            cipher.init(Cipher.DECRYPT_MODE, secretKeySpec);
            return new String(cipher.doFinal(Base64.getDecoder().decode(encryptedString)));
        } catch (Exception e) {
            System.out.println("Error while decrypting: " + e);
            return secretString;
        }
    }
}
