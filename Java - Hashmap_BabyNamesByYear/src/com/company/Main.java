package com.company;

import java.io.FileNotFoundException;
import java.io.IOException;
import java.net.MalformedURLException;
import java.util.*;

public class Main {

    /**
     * @param year
     * @return
     * @throws FileNotFoundException
     * @throws MalformedURLException
     */

    //loads the details from the text and saves to Arrays of girls and boys
    public static ArrayList mapMaker(int year) throws FileNotFoundException, MalformedURLException {
        String inputFile;
        switch (year) {
            case 2001:
                inputFile = new String("http://liveexample.pearsoncmg.com/data/babynameranking2001.txt");
                break;
            case 2002:
                inputFile = new String("http://liveexample.pearsoncmg.com/data/babynameranking2002.txt");
                break;
            case 2003:
                inputFile = new String("http://liveexample.pearsoncmg.com/data/babynameranking2003.txt");
                break;
            case 4:
                inputFile = new String("http://liveexample.pearsoncmg.com/data/babynameranking2004.txt");
                break;
            case 2005:
                inputFile = new String("http://liveexample.pearsoncmg.com/data/babynameranking2005.txt");
                break;
            case 2006:
                inputFile = new String("http://liveexample.pearsoncmg.com/data/babynameranking2006.txt");
                break;
            case 2007:
                inputFile = new String("http://liveexample.pearsoncmg.com/data/babynameranking2007.txt");
                break;
            case 2008:
                inputFile = new String("http://liveexample.pearsoncmg.com/data/babynameranking2008.txt");
                break;
            case 2009:
                inputFile = new String("http://liveexample.pearsoncmg.com/data/babynameranking2009.txt");
                break;
            case 2010:
                inputFile = new String("http://liveexample.pearsoncmg.com/data/babynameranking2010.txt");
                break;
            default:
                throw new IllegalStateException("Unexpected value: " + year);
        }
        try (Scanner input = new java.util.Scanner(new java.net.URL(inputFile).openStream())) {
            String line;
            Map<String, Integer> boys = new HashMap<>();
            Map<String, Integer> girls = new HashMap<>();
            ArrayList<Map<String, Integer>> kidMap = new ArrayList<>();
            while (input.hasNext()) {
                line = input.nextLine();
                String[] data = line.split("\t");
                Integer[] numList = new Integer[2];
                int rank = Integer.parseInt(data[0].trim());
                String boyName = data[1];
                numList[0] = rank;
                boys.put(boyName, rank);
                String girlName = data[3].trim();
                girls.put(girlName, rank);
                kidMap.add(boys);
                kidMap.add(girls);
            }
            input.close();
            return kidMap;
        } catch (IOException e) {
            e.printStackTrace();
            return null;
        }
    }

    /**
     * @param name
     * @param gender
     * @param kidMap
     * @return
     */
    //Checks whether the given name exists and retrieves the corresponding rank
    public static int getRank(String name, String gender, ArrayList<HashMap<String, Integer>> kidMap) {
        int rank;
        if (gender.equalsIgnoreCase("boy")) {
            HashMap<String, Integer> boy = kidMap.get(0);
            if (boy.containsKey(name)) {
                rank = boy.get(name);
                return rank;
            }
        }
        if (gender.equalsIgnoreCase("girl")) {
            HashMap<String, Integer> girl = kidMap.get(1);
            if (girl.containsKey(name)) {
                rank = girl.get(name);
                return rank;
            }
        }
        return 0;
    }

    /**
     * @param args
     * @throws FileNotFoundException
     * @throws MalformedURLException
     */

    public static void main(String[] args) throws FileNotFoundException, MalformedURLException {
        Scanner input = new Scanner(System.in);
        while (true) {
            System.out.println("Please enter the following details to get the rank of a how popular a child's name was in a specific year. ");
            System.out.print("Enter Year: ");
            while (!input.hasNextInt()){
                System.out.println("Please enter a year between 2001 and 2010:");
                input.nextLine();
            }
            int year = input.nextInt();
            while (year < 2001 || year > 2010) {
                System.out.println("Sorry you can only search between 2001 and 2010. Please enter a year between those.");
                year = input.nextInt();
            }
            System.out.print("Enter Name: ");
            String name = input.next();

            //forces proper capitalization/ lower for first letter to comply with lists.

            String[] nameArray = name.split("");
            for (int i = 0; i < nameArray.length; i++) {
                nameArray[i] = nameArray[i].toLowerCase();
            }
            nameArray[0] = nameArray[0].toUpperCase();
            name = "";
            for (int i = 0; i < nameArray.length; i++) {
                name = name.concat(nameArray[i]);
                System.out.println(name);
            }
            System.out.print("Enter Gender(boy/girl): ");
            String gender = input.next();
            System.out.println("");
            int rank = getRank(name, gender, mapMaker(year));
            if (rank != 0) {
                System.out.println(name + " is ranked #" + rank);
            } else {
                System.out.println("Name not available in the ranking.");
            }
            System.out.println("Press (1) to search again or (0) to quit");
            int repeat = input.nextInt();
            if(repeat == 0){
                break;
            }
        }
        input.close();
    }
}