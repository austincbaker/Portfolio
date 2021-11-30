package com.company;

import javax.crypto.BadPaddingException;
import javax.crypto.Cipher;
import javax.crypto.IllegalBlockSizeException;
import javax.crypto.NoSuchPaddingException;
import javax.crypto.spec.SecretKeySpec;
import java.io.*;
import java.net.InetAddress;
import java.net.Socket;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.spec.InvalidKeySpecException;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Arrays;
import java.util.Base64;
import java.util.Scanner;
import java.util.StringTokenizer;

public class AustinClient {

    final static String password = "Password1234#";
    //public static AustinPassSec ps = new AustinPassSec();
    final static int ServerPort = 57392;
    public static void main(String[] args) throws UnknownHostException, IOException, InterruptedException, NoSuchAlgorithmException, IllegalBlockSizeException, NoSuchPaddingException, BadPaddingException, InvalidKeyException {
        //instantiate and create keys for client
        ClientRsa rsa= new ClientRsa();
        rsa.keyGen();
        String[] keyList = rsa.getKeyStrings();
        String publicKey = keyList[0];
        //System.out.println("Public Key:: "+publicKey);
        String privKey = keyList[1];
        //System.out.println("Private Key:: "+privKey);

        Scanner scn = new Scanner(System.in);

        // getting localhost ip
        InetAddress ip = InetAddress.getByName("localhost");
        // establish the connection
        Socket s = new Socket(ip, ServerPort);
        // obtaining input and out streams
        DataInputStream dis = new DataInputStream(s.getInputStream());
        DataOutputStream dos = new DataOutputStream(s.getOutputStream());

        //send public key to the server
        dos.writeUTF(publicKey);
        System.out.println("Public Key:: "+publicKey+ "\n");
        //System.out.println("\nPublic Key Sent to server");

        //obtain RSA encrypted password from the server
        String encryptedPassword = dis.readUTF();
        System.out.println("Encrypted Password from the server:: "+encryptedPassword + "\n");

        //decrypt the password from the server
        String decryptedPassword = ClientRsaU.decrypt(encryptedPassword,privKey);
        System.out.println("Decrypted Password from the server:: "+decryptedPassword);

        //instantiate AES
        ClientAes aes = new ClientAes();
/*
        String aesKey = aes.setKey(decryptedPassword);
        String aesTestString = "\nThis is testing the AES encryption";
        String aesTestEncryptedOutput = aes.encrypt(aesTestString,aesKey);
        System.out.println(aesTestEncryptedOutput);
        String aesTestDecryptOutput = aes.decrypt(aesTestEncryptedOutput, aesKey);
        System.out.println(aesTestDecryptOutput);

        System.out.println("\nAES Key:: "+aesKey);*/
        dos.writeUTF("received");
        //System.out.println("received sent");


        // sendMessage thread
        Thread sendMessage = new Thread(() -> {
            Scanner scn1 = new Scanner(System.in);
            String message;
            while (true) {
                // read the message to deliver.
                String msg = scn1.nextLine();
                try {
                    message = aes.encrypt(msg, decryptedPassword);
                    dos.writeUTF(message);
                } catch (IOException e) {
                    e.printStackTrace();
                }
                //System.out.println("Message being sent to the server: " + msg + "\n");
                /*if(msg.length() > 0) {

                    //System.out.println("Encrypted msg being sent to server: " + message + "\n");

                }*/
                assert true;
            }
        });

        // readMessage thread
        Thread readMessage = new Thread(new Runnable()
        {
            @Override
            public void run() {
                while (true) {
                    try {
                        // receive the message from the server
                        String receivedMsg = dis.readUTF();

                        System.out.println("The encrypted message we received: " + receivedMsg + "\n");

                        //split the message into sender and message
                        StringTokenizer stringTokenizer = new StringTokenizer(receivedMsg, "@");
                        String messageSender = stringTokenizer.nextToken().trim();
                        String encryptedMsg = aes.decrypt(stringTokenizer.nextToken().trim(),password);
                        // remove the original @recipient
                        stringTokenizer = new StringTokenizer(encryptedMsg, "@");
                        String decryptedMessage = stringTokenizer.nextToken();
                        System.out.println("The real message!:\n");
                        System.out.println(messageSender +" " + decryptedMessage);

                    } catch (IOException e) {
                        System.out.println("The error is in decrypt");

                        e.printStackTrace();
                    }
                }
            }
        });
        String start = dis.readUTF();
        System.out.println("Looking for Enter Name");
        System.out.println(start);
        while(!start.equalsIgnoreCase("Enter your Name: "))
        {
            start = dis.readUTF();
            System.out.println(start);
        }
        sendMessage.start();
        readMessage.start();
    }
}
class ClientRsa {

    public PrivateKey privateKey;
    public PublicKey publicKey;


    public void keyGen() throws IOException, NoSuchAlgorithmException {
        KeyPairGenerator keyGen = KeyPairGenerator.getInstance("RSA");
        keyGen.initialize(1024);
        KeyPair pair = keyGen.generateKeyPair();
        this.privateKey = pair.getPrivate();
        this.publicKey = pair.getPublic();
        writeToFile("C:/keyHolder/publicKey", getPublicKey().getEncoded());
        writeToFile("C:/keyHolder/privateKey", getPublicKey().getEncoded());
    }

    public void writeToFile(String path, byte[] key) throws IOException {
        File f = new File(path);
        f.getParentFile().mkdirs();

        FileOutputStream fos = new FileOutputStream(f);
        fos.write(key);
        fos.flush();
        fos.close();
    }

    public PrivateKey getPrivateKey() {
        return privateKey;
    }

    public PublicKey getPublicKey() {
        return publicKey;
    }

    public void setPrivateKey(PrivateKey privateKey) {
        this.privateKey = privateKey;
    }

    public void setPublicKey(PublicKey publicKey){
        this.publicKey = publicKey;
    }

    public String[] getKeyStrings(){
        String[] s = new String[2];
        s[0] = Base64.getEncoder().encodeToString(getPublicKey().getEncoded());
        s[1] = Base64.getEncoder().encodeToString(getPrivateKey().getEncoded());
        return s;
    }
}
class ClientRsaU {

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

    public static byte[] encrypt(String data, String publicKey) throws BadPaddingException, IllegalBlockSizeException, InvalidKeyException, NoSuchPaddingException, NoSuchAlgorithmException {
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

    public static void main(String[] args) throws IllegalBlockSizeException, InvalidKeyException, NoSuchPaddingException, BadPaddingException {
        try {
            String encryptedString = Base64.getEncoder().encodeToString(encrypt("Test", publicKey));
            System.out.println(encryptedString);
            String decryptedString = ClientRsaU.decrypt(encryptedString, privateKey);
            System.out.println(decryptedString);
        } catch (NoSuchAlgorithmException e) {
            System.err.println(e.getMessage());
        }

    }
}
class ClientAes {

    private SecretKeySpec secretKeySpec;
    //todo: Get the public key of the person(s) the message is being sent to
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
            System.out.println("Error while encrypting: " + e.toString());
        }
        return null;
    }

    public String decrypt(String encryptedString, String secretString) {
        try {
            setKey(secretString);
            Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5PADDING");
            cipher.init(Cipher.DECRYPT_MODE, secretKeySpec);
            return new String(cipher.doFinal(Base64.getDecoder().decode(encryptedString)));
        } catch (Exception e) {
            System.out.println("Error while decrypting: " + e);
        }
        return null;
    }
}
