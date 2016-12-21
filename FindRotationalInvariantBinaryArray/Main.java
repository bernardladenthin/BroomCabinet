import java.util.List;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Arrays;
import java.util.Map;
import java.util.HashMap;

public class Main {
    
    static boolean isNotInMap(Map<List<Boolean>, List<List<Boolean>>> map, List<List<Boolean>> combinationRotations) {
        for (List<Boolean> rotation : combinationRotations) {
            if (map.containsKey((rotation))) {
                return false;
            }
        }
        return true;
    }
    
    static Map<List<Boolean>, List<List<Boolean>>> generateRotationalInvariantCombinations(int size) {
        Map<List<Boolean>, List<List<Boolean>>> rotationalInvariant = new HashMap<>();
        List<List<Boolean>> combinations = generateCombinations(size);
        for (List<Boolean> combination : combinations) {
            List<List<Boolean>> combinationRotations = generateAllPossibleRotations(combination);
            if (isNotInMap (rotationalInvariant, combinationRotations)) {
                rotationalInvariant.put(combination, combinationRotations);
            }
        }
        return rotationalInvariant;
    }
    
    // from http://stackoverflow.com/questions/27007752/creating-all-possible-ways-of-a-boolean-array-of-size-n
    static List<List<Boolean>> generateCombinations (int size) {
        List<List<Boolean>> combinations = new ArrayList<>();
        for (int i = 0; i < Math.pow(2, size); i++) {
            String bin = Integer.toBinaryString(i);
            while (bin.length() < size) {
                bin = "0" + bin;
            }
            char[] chars = bin.toCharArray();
            Boolean[] boolArray = new Boolean[size];
            for (int j = 0; j < chars.length; j++) {
                boolArray[j] = chars[j] == '0' ? true : false;
            }
            combinations.add(Arrays.asList(boolArray));
        }
        return combinations;
    }
    
    static List<List<Boolean>> generateAllPossibleRotations(List<Boolean> toRotate) {
        List<List<Boolean>> rotations = new ArrayList<>();
        for (int i = 0; i < toRotate.size(); i++) {
            List<Boolean> mutable = new ArrayList<>(toRotate);
            Collections.rotate(mutable, i);
            rotations.add(mutable);
        }
        return rotations;
    }
    
    static boolean isRotationalInvariant(List<Boolean> array1, List<Boolean> array2) {
        if (array1.size() != array2.size()) {
            throw new IllegalArgumentException("Booth arrays must have the same length.");
        }
        List<List<Boolean>> rotations = generateAllPossibleRotations(array1);
        for (List<Boolean> rotation : rotations) {
            if (rotation.equals(array2)) {
                return false;
            }
        }
        
        return true;
    }

     public static void main(String []args){
        {
            System.out.println("## example 1");
            List<Boolean> toRotate = Arrays.asList(new Boolean[] { true, true, false, false });
            System.out.println(generateAllPossibleRotations(toRotate));
        }
        {
            System.out.println("## example 2");
            List<Boolean> toRotate   = Arrays.asList(new Boolean[] { true, true, false, false });
            List<Boolean> isNotEqual = Arrays.asList(new Boolean[] { true, true, true, false });
            // should be true
            System.out.println(isRotationalInvariant(toRotate, isNotEqual));
        }
        {
            System.out.println("## example 3");
            List<Boolean> toRotate = Arrays.asList(new Boolean[] { true, true, false, false });
            List<Boolean> isEqual  = Arrays.asList(new Boolean[] { true, false, false, true });
            // should be false
            System.out.println(isRotationalInvariant(toRotate, isEqual));
        }
        {
            System.out.println("## example 4");
            List<List<Boolean>> combinations = generateCombinations(4);
            System.out.println(combinations);
        }
        {
            System.out.println("## example 5 (4 bit)");
            Map<List<Boolean>, List<List<Boolean>>> combinations = generateRotationalInvariantCombinations(4);
            System.out.println("found combinations for 4 bit:" + combinations.size());
            System.out.println(combinations.keySet());
        }
        {
            System.out.println("## example 6 (8 bit)");
            Map<List<Boolean>, List<List<Boolean>>> combinations = generateRotationalInvariantCombinations(8);
            System.out.println("found combinations for 8 bit:" + combinations.size());
            System.out.println(combinations.keySet());
        }
        
     }
}
