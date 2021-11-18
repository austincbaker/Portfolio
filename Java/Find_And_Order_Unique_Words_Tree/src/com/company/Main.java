package com.company;

import java.util.Scanner;
import java.util.Set;
import java.io.File;
import java.util.TreeSet;

public class Main {
    /**
     * @author Austin Baker
     * @param args
     *
     */
    public static void main(String[] args) {
        File f = new File("fstein.txt");
        try (Scanner scan = new Scanner(f)) {
            int listSize = (int) f.length();
            Set<String> tree = new TreeSet<>();
            String[] s = new String[listSize];
            int i = 0;
            tree.add(scan.nextLine());
            while (scan.hasNext()) {
                String alpha = scan.next();
                tree.add(alpha);
            }
            for (String a : tree) {
                System.out.print(a + ", ");
            }

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
