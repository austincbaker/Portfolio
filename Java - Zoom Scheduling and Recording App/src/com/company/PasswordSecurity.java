package com.company;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.math.BigInteger;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.security.spec.InvalidKeySpecException;
import java.util.Random;

public class PasswordSecurity {

    public String createRandomPassword() throws NoSuchAlgorithmException, InvalidKeySpecException {
        char[] charsList = "aabcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!@#$%&*()-+=?~`}{][".toCharArray();
        StringBuilder password = new StringBuilder();
        for(int i = 0; i < 16; i++){
            Random random = new Random();
            char passChar = charsList[random.nextInt(charsList.length)];
            password.append(passChar);
        }
        String securedPassword = createPasswordHash(password.toString());
        return securedPassword;
    }

    public String createPasswordHash(String password) throws NoSuchAlgorithmException, InvalidKeySpecException {
        int iterations = 1000;
        char[] charsArray = password.toCharArray();
        byte[] saltArray = getSalt();

        PBEKeySpec spec = new PBEKeySpec(charsArray, saltArray, iterations, 64 * 8);
        SecretKeyFactory skf = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA1");
        byte[] hashArray = skf.generateSecret(spec).getEncoded();
        return iterations + ":" + toHex(saltArray) + ":" + toHex(hashArray);
    }

    private static byte[] getSalt() throws NoSuchAlgorithmException
    {
        SecureRandom sr = SecureRandom.getInstance("SHA1PRNG");
        byte[] saltArray = new byte[16];
        sr.nextBytes(saltArray);
        return saltArray;
    }

    private static String toHex(byte[] array) throws NoSuchAlgorithmException
    {
        BigInteger bi = new BigInteger(1, array);
        String hex = bi.toString(16);
        int paddingLength = (array.length * 2) - hex.length();
        if(paddingLength > 0)
        {
            return String.format("%0"  +paddingLength + "d", 0) + hex;
        }else{
            return hex;
        }
    }

    public boolean checkPassword(String enteredPassword, String storedPassword) throws NoSuchAlgorithmException, InvalidKeySpecException
    {
        String[] parts = storedPassword.split(":");
        int iterations = Integer.parseInt(parts[0]);
        byte[] saltArray = fromHex(parts[1]);
        byte[] hashArray = fromHex(parts[2]);

        PBEKeySpec spec = new PBEKeySpec(enteredPassword.toCharArray(), saltArray, iterations, hashArray.length * 8);
        SecretKeyFactory skf = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA1");
        byte[] testHash = skf.generateSecret(spec).getEncoded();

        int diff = hashArray.length ^ testHash.length;
        for(int i = 0; i < hashArray.length && i < testHash.length; i++)
        {
            diff |= hashArray[i] ^ testHash[i];
        }
        return diff == 0;
    }
    private static byte[] fromHex(String hex) throws NoSuchAlgorithmException
    {
        byte[] byteList = new byte[hex.length() / 2];
        for(int i = 0; i< byteList.length ; i++)
        {
            byteList[i] = (byte)Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return byteList;
    }

}
