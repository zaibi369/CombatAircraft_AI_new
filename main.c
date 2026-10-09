// #include <math.h>
// #include <stdbool.h>
// #include <stdio.h>
// #include <string.h>
// #include <windows.h>


// // // SetConsoleOutputCP(65001)

// int main() {

// FIRST PROGRAM:::

//   // SetConsoleOutputCP(65001)
//   int age = 0;
//   float gpa = 0.0f;
//   char grade = '\0';
//   char name[30] = "";

//   printf("Enter your age: ");
//   scanf("%3s", &age);

//   printf("Enter your gpa: ");
//   scanf("%3s", &gpa);

//   printf("Enter your grade: ");
//   scanf(" %c", &grade);
//   getchar();
//   printf("Enter your full name: ");
//   fgets(name, sizeof(name), stdin);
//   name[strlen(name) - 1] = '\0';

//   printf("\n");
//   printf("Name: %s\n", name);
//   printf("Age: %3s\n", age);
//   printf("GPA: %.2f\n", gpa);
//   printf("Grade: %c\n", grade);
//   return 0;
// }

// int main() {
//   // SHOPPING CART PROGRAM:::

//   char item[50] = "";
//   float price = 0.0f;
//   int quantity = 0;
//   char curr = '$';
//   float total = 0.0f;

//   printf("What item would u like to buy?: ");
//   fgets(item, sizeof(item), stdin);
//   item[strlen(item) - 1] = '\0';

//   printf("What is the price for each item?: ");
//   scanf("%3s", &price);

//   printf("How many would u like to buy?: ");
//   scanf("%3s", &quantity);

//   total = price * quantity;
//   printf("\nYou have bought %3s %s,s\n", quantity, item);
//   printf("    The total is: %c%.2f", curr, total);

//   return 0;
// }

// int main() {
//   // Storage for the simple words
//   char hero[50] = "";
//   char enemy[50] = "";
//   char helper[50] = "";
//   char food[50] = "";

//   char action1[50] = "";
//   char action2[50] = "";
//   char action3[50] = "";
//   char action4[50] = "";

//   char toy[50] = "";
//   char spot1[50] = "";
//   char spot2[50] = "";

//   char look1[50] = "";
//   char look2[50] = "";
//   char look3[50] = "";
//   char look4[50] = "";

//   printf("=== THE CRAZY ADVENTURE GENERATOR ===\n\n");

//   // --- SIMPLE QUESTIONS ---
//   printf(
//       "1. Enter a main character (Hint: Shrek, a fat cat, a giant banana):
//       ");
//   fgets(hero, sizeof(hero), stdin);
//   hero[strcspn(hero, "\n")] = '\0';

//   printf("2. Enter a bad guy (Hint: a giant spider, your teacher, an angry "
//          "baby): ");
//   fgets(enemy, sizeof(enemy), stdin);
//   enemy[strcspn(enemy, "\n")] = '\0';

//   printf("3. Enter a funny friend (Hint: SpongeBob, a friendly ghost, a "
//          "minion): ");
//   fgets(helper, sizeof(helper), stdin);
//   helper[strcspn(helper, "\n")] = '\0';

//   printf("4. Enter a type of food (Hint: a cheesy pizza, a smelly taco, a "
//          "rotten egg): ");
//   fgets(food, sizeof(food), stdin);
//   food[strcspn(food, "\n")] = '\0';

//   printf("\n5. Enter a funny way to move (Hint: dance, crawl, fly backward):
//   "); fgets(action1, sizeof(action1), stdin); action1[strcspn(action1, "\n")]
//   = '\0';

//   printf("6. Enter a silly attack word (Hint: tickle, slap, lick, sit on):
//   "); fgets(action2, sizeof(action2), stdin); action2[strcspn(action2, "\n")]
//   = '\0';

//   printf(
//       "7. Enter a magic power action (Hint: turn into ice, explode, scream):
//       ");
//   fgets(action3, sizeof(action3), stdin);
//   action3[strcspn(action3, "\n")] = '\0';

//   printf("8. Enter a quick escape action (Hint: vanish, roll away, melt): ");
//   fgets(action4, sizeof(action4), stdin);
//   action4[strcspn(action4, "\n")] = '\0';

//   printf("\n9. Enter a random object/toy (Hint: a rubber duck, a smelly sock,
//   "
//          "a pillow): ");
//   fgets(toy, sizeof(toy), stdin);
//   toy[strcspn(toy, "\n")] = '\0';

//   printf("10. Enter a fun place (Hint: Disneyland, the moon, a toilet bowl):
//   "); fgets(spot1, sizeof(spot1), stdin); spot1[strcspn(spot1, "\n")] = '\0';

//   printf("11. Enter a weird place (Hint: a trash can, a dark cave, a "
//          "refrigerator): ");
//   fgets(spot2, sizeof(spot2), stdin);
//   spot2[strcspn(spot2, "\n")] = '\0';

//   printf(
//       "\n12. Enter a descriptive word (Hint: smelly, shiny, extremely lazy):
//       ");
//   fgets(look1, sizeof(look1), stdin);
//   look1[strcspn(look1, "\n")] = '\0';

//   printf("13. Enter a descriptive word (Hint: tiny, super fat, neon green):
//   "); fgets(look2, sizeof(look2), stdin); look2[strcspn(look2, "\n")] = '\0';

//   printf("14. Enter a scary word (Hint: ugly, spooky, brain-rotted): ");
//   fgets(look3, sizeof(look3), stdin);
//   look3[strcspn(look3, "\n")] = '\0';

//   printf("15. Enter a funny mood word (Hint: crazy, confused, dramatic): ");
//   fgets(look4, sizeof(look4), stdin);
//   look4[strcspn(look4, "\n")] = '\0';

//   // --- BRAND NEW FUNNY STORY: THE WEIRD COOKING SHOW ---
//   printf("\n================ WELCOME TO THE FOOD FIGHT
//   ================\n\n");

//   printf("Welcome to the reality TV show 'Master Chef: Disaster Edition' "
//          "broadcasting live from %s!\n",
//          spot1);

//   printf("Our head chef, a %s %s, is attempting to bake a cake made
//   completely "
//          "out of %s.\n",
//          look1, hero, food);

//   printf("Suddenly, the grumpy celebrity judge, a %s %s, jumps onto the "
//          "kitchen table!\n",
//          look3, enemy);

//   printf("The judge screams, 'This food is garbage! I will now %s the kitchen
//   "
//          "staff!'\n",
//          action2);

//   printf("In a blind rage, the judge grabs a %s %s and throws it directly at
//   "
//          "the audience!\n",
//          look2, toy);

//   printf("Out of nowhere, the assistant chef %s dives across the room to
//   block "
//          "it while trying to %s gracefully.\n",
//          helper, action1);

//   printf("The cake suddenly begins to %s like a volcano, spraying hot, gooey
//   "
//          "%s everywhere!\n",
//          action3, food);

//   printf("Terrified of the mess, the judge has no choice but to %s out the "
//          "emergency exit.\n",
//          action4);

//   printf("The TV studio is totally ruined, leaving everyone feeling
//   incredibly "
//          "%s.\n",
//          look4);

//   printf("But hey, at least they won a lifetime supply of cooked snacks "
//          "located inside %s!\n",
//          spot2);

//   printf("\n==================== THE END ====================\n");

//   return 0;
// }

//   // --- BRAND NEW FUNNY STORY: THE SECRET AGENT MISSION ---
//   printf("\n================ TOP SECRET FILE ================\n\n");

//   printf("Secret Agent %s just woke up inside %s wrapped in a giant sheet of
//   "
//          "%s.\n",
//          hero, spot1, food);

//   printf("The evil mastermind, a %s %s, appeared on a giant screen laughing "
//          "maniacally.\n",
//          look3, enemy);

//   printf("'I have locked you in my trap!' the villain yelled. 'And soon, I "
//          "will %s the entire world!'\n",
//          action2);

//   printf("Suddenly, the ceiling shattered and %s came down on a rope, looking
//   "
//          "incredibly %s.\n",
//          helper, look1);

//   printf("The helper didn't bring any weapons. Instead, they pulled out a %s
//   "
//          "%s!\n",
//          look2, toy);

//   printf("With a loud battle cry, they threw the object at the control panel,
//   "
//          "causing it to %s instantly.\n",
//          action3);

//   printf("The building started shaking, forcing the bad guy to %s out the
//   back "
//          "door.\n",
//          action4);

//   printf("Agent %s broke free by using their signature move to %s through the
//   "
//          "wall.\n",
//          hero, action1);

//   printf("They both escaped just in time and hid safely inside %s, eating a "
//          "big bowl of %s.\n\n",
//          spot2, food);

//   printf("The world was saved, but the President was very %s about the mess "
//          "they left behind!\n",
//          look4);

//   printf("\n==================== THE END ====================\n");

//   return 0;
// }

// int main(){
//     // FUNCTION IN C::::

//   float x = 6.688;

//   // x = sqrt(x);
//   // x = pow(x, 4);
//   // x = round(x);
//   // x = ceil(x);
//   // x = floor(x);
//   // x = abs(x);
//   // x = log(x);
//   // x = sin(x);
//   // x = cos(x);
// //   x = tan(x);

//   printf("%3s", x);

//   return 0;

// }

// int main() {

// AREA FINDING PROGRAM::::

//   double radius = 0.0;
//   double area = 0.0;
//   double sur_area = 0.0;
//   double volume = 0.0;
//   const double PI = 3.14159;

//   printf("Enter the radius: ");
//   scanf("%.2lf", &radius);

//   area = PI * pow(radius, 2);
//   sur_area = 4 * PI * pow(radius, 2);
//   volume = (4.0 / 3.0) * PI * pow(radius, 3);

//   printf("Area: %.2lf\n", area);
//   printf("Surface area: %.2lf\n", sur_area);
//   printf("Volume: %.2lf\n", volume);

//   return 0;
// }

// int main() {

//   //     // COMPOUND INTEREST CALCULATOR:::

//   double principle = 0.0;
//   double rate = 0.0;
//   int years = 0;
//   int times_c = 0;
//   double total = 0.0;

//   printf("COMPOUND INTEREST CALCULATOOR::\n");

//   printf("Enter the principle (p): ");
//   scanf("%.2lf", &principle);

//   printf("Enter the intreset rate % (r):  ");
//   scanf("%.2lf", &rate);
//   rate = rate / 100;

//   printf("Enter the # of years (t): ");
//   scanf("%3s", &years);

//   printf("Enter the # of times compounded / year (n): ");
//   scanf("%3s", &times_c);

//   total = principle * pow(1 + rate / times_c, times_c * years);

//   printf("After %3s year/s, the total amount will be $%.2f.", years, total);

//   return 0;
// }

// #include <stdbool.h>
// #include <string.h>
// int main() {

//   // IF STAEMENTS::::

//   char name[50] = "";

//   printf("Enter your name: ");
//   fgets(name, sizeof(name), stdin);
//   name[strlen(name) -1] = '\0';

//   if (strlen(name) == 0) {
//     printf("You did not enter your name: ");
//   } else {
//     printf("Hello %s", name);
//   }

//   return 0;
// }

// int main(){

//   // WEIGHT CONVERTER PROGRAMM::::

//   int choice = 0;
//   float pounds = 0.0f;
//   float kilograms = 0.0f;

//   printf("WEIGHT CONVERWSION CALCULATOR:::\n\n");
//   printf("  1 > KILOGRAMS TO POUNDS::\n");
//   printf("  2 > POUNDS TO KILOGRAMS::\n\n");
//   printf("Enter your choice | 1 || 2 |: ");
//   scanf("%3s", &choice);
//   if(choice == 1){
//     // kilo to pd;
//     printf("Enter the weight in kilograms: ");
//     scanf("%3s", &kilograms);
//     pounds = kilograms * 2.20462;
//     printf("%.2f  kilograms is equal to %.2f\n", kilograms , pounds);

//   }
//   else if(choice == 2){
//     // pd to kilo;
//     printf("Enter the weight in pounds: ");
//     scanf("%3s", &pounds);
//     kilograms = pounds / 2.20462;
//     printf("\n  %.2f pounds is equal to %.2f.\n\n", pounds, kilograms);
//   }
//   else{
//     printf("Invalid choice , please enter 1 or 2 !\n");
//   }

//   return 0;
// }

// int main() {

//   // TEMPERATURE CONVERSION PROGRAM:::

//   SetConsoleOutputCP(65001);

//   char choice[10] = "";
//   float fn = 0.0f;
//   float cs = 0.0f;
//   float kl = 0.0f;

//   printf("TEMPERATURE CONVERSION PROGRAM::\n\n");
//   printf("C>F: CELSIUS TO FAHRENHEIT::\n\n");
//   printf("F>C:: FAHRENHEIT TO CELSIUS::\n\n");
//   printf("K>C:: KALVING TO CELSIUS::\n\n");
//   printf("C>K:: CELSIUS TO KALVIN::\n\n");
//   printf("K>F:: KALVIN TO FAHRENEIT::\n\n");
//   printf("F>K:: FAHRENEIT TO KALVIN::\n\n");

//   printf("  Is the temp in CELSIUS(C) / FAHRENHEIT(F) / KALVIN(K)? (use "
//          "capital C/F/K like C>F or F>C only): ");
//   scanf("%3s", choice);

//   if (strcmp(choice, "C>F") == 0) {
//     // C to F:
//     printf("Enter the temperature in CELSIUS: ");
//     scanf("%f", &cs);
//     fn = (cs * 9 / 5) + 32;
//     printf("  %.2f°C conversion to Fahrenheit: %.2f°F\n", cs, fn);

//   } else if (strcmp(choice, "F>C") == 0) {
//     // F to C:
//     printf("Enter the tempreture in  FAHRENHEIT: ");
//     scanf("%f", &fn);
//     cs = (fn - 32) * 5 / 9;
//     printf("  %.2f°F conversion to Celsius: %.2f°C\n", fn, cs);

//   } else if (strcmp(choice, "K>C") == 0) {
//     // K TO C:
//     printf("Enter the tempreture in Kelvin: ");
//     scanf("%f", &kl);
//     cs = (kl - 273.15);
//     printf("  %.2f K conversion to Celsius: %.2f°C\n", kl, cs);

//   } else if (strcmp(choice, "C>K") == 0) {
//     //  C TO K:
//     printf("Enter the tempreture in Celsius: ");
//     scanf("%f", &cs);
//     kl = (cs + 273.15);
//     printf("  %.2f°C conversion to Kelvin: %.2f K\n", cs, kl);

//   } else if (strcmp(choice, "K>F") == 0) {
//     // K TO F:
//     printf("Enter the tempreture in Kelvin: ");
//     scanf("%f", &kl);
//     fn = (kl - 273.15) * 9 / 5 + 32;
//     printf("  %.2f K conversion to Fahrenheit: %.2f°F\n", kl, fn);

//   } else if (strcmp(choice, "F>K") == 0) {
//     // F TO K:
//     printf("Enter the tempreture in Fahrenheit: ");
//     scanf("%f", &fn);
//     kl = (fn - 32) * 5 / 9 + 273.15;
//     printf("  %.2f°F conversion to Kelvin: %.2f K\n", fn, kl);

//   } else {
//     printf("Invalid choice or input !.");
//   }

//   return 0;
// }

// int main() {

//   SetConsoleOutputCP(65001);

//   //  SWITCH  = An alternative to usign many if-else statements.
//   // More efficient W/ fixed integer values.

//   char dow = '\0';
//   printf("Enter a day of week (M, T, W, R, F, S, U): ");
//   scanf("%c", &dow  );

//   switch(dow){
//     case 'M':
//       printf("It is Monday!");
//     break;
//     case 'T':
//       printf("It is Tuesday!");
//       break;
//     case 'W':
//       printf("It is Wednesday!");
//     break;
//     case 'R':
//       printf("It is Thursday!");
//       break;
//     case 'F':
//       printf("It is Friday!");
//     break;
//     case 's':
//       printf("It is Saturday!");
//       break;
//     case 'U':
//       printf("It is Sunday!");
//       break;
//     default:
//       printf("PLEASE ONLY ENTER character (M, T, W, R, F, S, U)");
//   }
//   return 0;
// }

// int main() {
//   float price = 10.00;
//   char iss = '\0'; // 10% discount if student::
//   char is = '\0'; // 20% discount if senior
//   // student = $9
//   // senior = %8
//   // senior + student = %7
//   printf("Are u a student ? (y/n): ");
//   scanf(" %c", &iss);
//   printf("Are u a senior above 60? (y/n): ");
//   scanf(" %c", &is);
//   if(iss == 'y' && is == 'y'){
//        printf("You get a student discount of 10%%!.\n");
//        printf("You also get a senior discount of 20%%!.\n");
//        price *= 0.7;
//   } else if(is == 'y'){
//        printf("You get a senior discount of 20%%!.\n");
//        price *= 0.8;
//   } else if(iss == 'y'){
//        printf("You get a student discount of 10%%!.\n");
//        price *= 0.9;
//   } else if(iss == 'n' && is == 'n'){
//        printf("");
//   }else{
//        printf("Please type exactly (y or n)");
//   }
//     printf("The prcie of the ticket is: $%.2f!.\n", price);
//   return 0;
// }

// #include <stdio.h>
// #include <math.h>

// int main(){

//        // SIMPLE CALCULATOR PROGRAM:::
//        char op = '\0';
//        double n1 = 0.0;
//        double n2 = 0.0;
//        double result = 0.0;
//        printf("Enter your operator [+  -  *  /  log(L) sq/root(Q) power(P)
//        cos(C) tan(T) sin(S) ]: "); scanf(" %c", &op); printf("Enter your
//        first number (x): "); scanf(" %lf", &n1); printf("Enter your second or
//        n for 'vi' number (y): "); scanf(" %lf", &n2); if (op == '+'){
//               result = n1 + n2;
//               printf("%.2lf plus %.2lf equals: %.3lf.", n1, n2, result);
//        }else if(op == '-'){
//               result = n1 - n2;
//               printf("%.2lf minus %.2lf equals: %.3lf.", n1, n2, result);
//        }else if(op == '*'){
//               result = n1 * n2;
//               printf("%.2lf times %.2lf equals: %.3lf.", n1, n2, result);
//        }else if(op == '/'){
//               result  = n1 / n2;
//               printf("%.2lf divided by %.2lf equals: %.3lf.", n1, n2,
//               result);
//        }else if(op == 'L' && n2 == 0.0){
//               result = log(n1);
//               printf("%.2lf log equals: %.3lf.", n1, result);
//        } else if (op == 'T' && n2 == 0.0) {
//               result = tan(n1);
//               printf("tan(%.2lf) equals: %.3lf.", n1, result);
//        }else if(op == 'C' && n2 == 0.0){
//               result = cos(n1);
//               printf("cos(%.2lf) equals: %.3lf.", n1, result);
//        }else if(op == 'S' && n2 == 0.0){
//               result = sin(n1);
//               printf("sin(%.2lf)  equals: %.3lf.", n1, result);
//        }else if(op == 'Q' && n2 == 0.0){
//               result = sqrt(n1);
//               printf("sqrt(%.2lf)  equals: %.3lf.", n1, result);
//        }else if(op == 'P'){
//               result = pow(n1, n2);
//               printf("%.2lf with the power %.2f equals: %.3lf.", n1, n2,
//               result);
//        }else{
//               printf("Invalid input or invalid operation!..");
//        }
// return 0;
// }

// int main() {
//   bool iss = true;

// //   LOGICAL OPERATORS  = USED TO COMBINE OR MODIFY BOOLEAN EXPRESSION::::

//   if (!iss) {
//     printf("It is cloudy outside.");
//   } else {
//     printf("It is sunny outdie. ");
//   }
//   return 0;
// }

// void CtoF(double celsius) {
//   double fahrenheit = 0.00;
//   fahrenheit = (celsius * 9 / 5) + 32;
//   printf("%.2lf°C is %.2lf°F.\n", celsius, fahrenheit);
// }
// int main() {

//   SetConsoleOutputCP(65001);
//   // FUNCTIONS = A REUSABLE SECTION OF CODE THAT CAN BE INVOKED "CALLED".
//   //  ARGUMENTS CAN BE SENT TO A FUNCTION SO THAT IT CAN USE THEM.
// //   double input = 0000.1333;
//   CtoF(123);
//   return 0;
// }

// int getmax(int x, int y){
//        if(x >= y){
//               return x;
//        }else{
//               return y;
//        }
// }

//     int main() {
//   // return = RETURNS A VALUE BACK TO WHERE YOU CALL A function
//        int max = getmax(2, 6a);

//        printf("%d", max);

//   return 0;
// }

// // int result = 0; // GLOBAL SCOPRE (HARD TO DEBUG)

// int sub(int x, int y) {
//   int result = x - y; //DIFFERENT SCOPE
//   return result;
// }
// int add(int x, int y) {
//   int result = x + y; //DIFFERENT SCOPE
//   return result;
// }
// int main() {
//   // variable scope = REFERS TO WHERE A VARIABLE IS RECOGNIZED AND
//   ACCESSIBLE.
//   // VARIABLES CAN SHARE THE SAME NAME IS THEY ARE IN DIFFERENT SCOPES {}

//   int x = 5; //LOCAL SCOPRE
//   int y = 6;

//   int result = sub(x, y);
//   printf("%d", result);

//   return 0;
// }

// // FUNCTION PROTOTYPE = PROVIDE THE COMPILAR W/ INFORMATION ABOUT A
// FUNCTION'S:
// // NAME, RETURN TYPE, AND PARAMETERS BEFORE ITS ACTUAL DEFINITION. ENABLES
// TYPE
// // CHECKING AND ALLOWS FUNCTION TO BE USED BEFORE THEY ARE DEFINED. IMPROVE
// // READABILITY, ORGANIZATION, AND HELPS PREVENT ERRORS::::

// void hello(char name[], int age);
// bool agecheck(int age);

// int main() {
//   hello("spongebob", 30);

//   agecheck(15);
//   return 0;
// }

// void hello(char name[], int age) {
//   printf("hello %s\n", name);
//   printf("You are %d years old\n", age);
// }

// bool agecheck(int age) {
//   if (age >= 16) {
//     printf("You ARE old enough to work at krusty krab");
//   } else {
//     printf("You are NOT old enough to work at krusty krab.");
//   }
// }

// // while loop = CONTINUE SOME CODE WHILE THE CONDITION REMAINS TRUE.
// CONDITION
// // MUST BE TRUE FOR US TO ENTER WHIE LOOP::::

// #include <stdio.h>
// #include <stdlib.h>
// #include <time.h>

// int main() {

//   srand(time(NULL));
//   int max = 100;
//   int min = 50;

//   int random = (rand() % (max - min + 1)) + min;
//   printf("%d", random);

//   return 0;
// }

// #include <stdio.h>
// #include <stdlib.h>
// #include <time.h>

// int getuserchoice();
// int getcomputerchoice();
// int checkwinner(int userchoice, int computerchoice);

// int main() {
//   srand(time(NULL));
//   printf("*** ROCK PAPER SCISSORS GAME ***");
//   int attempts = 0;
//   int win_count = 0;

//   do {
//     int uchoice = getuserchoice();
//     int cchoice = getcomputerchoice();

//     switch (uchoice) {
//     case 1:
//       printf("    YOU CHOSE ROCK . \n");
//       break;
//     case 2:
//       printf("    YOU CHOSE PAPER .\n");
//       break;
//     case 3:
//       printf("    YOU CHOSE SCISSORS .\n");
//       break;
//     }
//     switch (cchoice) {
//     case 1:
//       printf("    COMPUTER CHOSE ROCK . \n");
//       break;
//     case 2:
//       printf("    COMPUTER CHOSE PAPER .\n");
//       break;
//     case 3:
//       printf("    COMPUTER CHOSE SCISSORS .\n");
//       break;
//     }
//     win_count += checkwinner(uchoice, cchoice);
//     attempts++;
//   } while (attempts != 10);
//   printf("\n=========================================\n");
//   printf("  GAME OVER! You won %d out of 10 rounds.\n", win_count);
//   printf("=========================================\n");

//   return 0;
// }

// int getuserchoice() {
//   int choice;
//   do {
//     printf("\n  1 > for ROCK . \n");
//     printf("  2 > for PAPER . \n");
//     printf("  3 > for SCISSORS . \n");
//     printf("ENTER YOUR CHOICE : ");
//     scanf("%d", &choice);
//   } while (choice < 1 || choice > 3);
//   return choice;
// }

// int getcomputerchoice() { return (rand() % 3) + 1; }

// int checkwinner(int userchoice, int computerchoice) {
//   if (userchoice == computerchoice) {
//     printf("    IT'S A TIE !. \n");
//     return 0;
//   } else if ((userchoice == 1 && computerchoice == 3) ||
//              (userchoice == 2 && computerchoice == 1) ||
//              (userchoice == 3 && computerchoice == 2)) {
//     printf("      HURRAY < YOU WON >\n");
//     return 1;
//   } else {
//     printf("   < YOU LOSE >\n");
//     return 0;
//   }
// }

// #include <stdio.h>
// #include <stdlib.h>
// #include <time.h>
// #include <windows.h>
// void checkbalance(float balance);
// float deposit();
// float withdraw(float);

// int main() {

//   SetConsoleOutputCP(65001);
//   // BANKING  PROGRAMM::::::::
//   // BANKING  PROGRAMM::::::::
//   // BANKING  PROGRAMM::::::::
//   int choice = 0;
//   float balance = 0.0f;
//   printf("|| *** WELCOME TO THE BANK *** ||");
//   do {
//     printf("\n\n     ::::BANKING OPTIONS::::\n");
//     printf("      1 > Check Balance  ::\n");
//     printf("      2 > Deposit Money  ::\n");
//     printf("      3 > Withdraw Money ::\n");
//     printf("      4 > Exit the Bank  ::\n");
//     printf("\n          * Enter your chocie  1|2|3|4 >=>> : ");
//     scanf("%d", &choice);

//     switch (choice) {

//     case 1:
//       checkbalance(balance);
//       break;
//     case 2:
//       balance += deposit();
//       break;
//     case 3:
//       balance -= withdraw(balance);
//       break;
//     case 4:
//       printf("\n    GOODBYE SUSSY ASS OF JACKIE_CHAIN SUCKER..::::\n");
//       break;
//     default:
//       printf("\nInvalid choice, Please select 1 - 4 :::");
//     }

//   } while (choice != 4);
//   return 0;
// }

// void checkbalance(float balance) {
//   printf("\nYour Current Balance Is:  $%.2f.\n", balance);
// }

// float deposit() {

//   float amount = 0.0f;

//   do {
//     printf(" Enter The Amount To Deposit : $");
//     scanf("%f", &amount);
//     if (amount <= 0) {
//       printf("\n    Invalid Amount OR Amount Can't be 0!.");
//     } else {
//       printf("\n\n      Successfully Deposited $%.2f\n", amount);
//       return amount;
//     }
//   } while (amount <= 0);
//   return 0.0f;
// }

// float withdraw(float balance) {
//   float amount = 0.0f;
//   do {
//     printf("\nEnter The Amount To Withdraw Or go back => (-7): $");
//     scanf("%f", &amount);
//     if(amount == -7){
//      return 0.0f;
//     }else if(amount <= 0) {
//       printf("\n    Invalid Amount OR Amount Can't be Zero!.");
//     } else if (amount > balance) {
//       printf("\n    Insufficient Funds!, Your Balance is $%.2f\n", balance);
//     } else {
//       printf("\n\n    Successfully Withdrawn $%.2f\n", amount);
//     }
//   } while (amount <= 0 || amount > balance);
//   return amount;
// }

// #include <stdio.h>
// #include <windows.h>
// int main() {

//   SetConsoleOutputCP(65001);
//   // array = A FIXED-SIZED COLLECTION OF ELEMENTS OF THE SAME DATATYPE
//   (SIMILAR
//   // TO A variable, BUT IT HOLDS MORE THAN ! VALUE ):::::::

//   int numbers[] = {10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120};
//   char grades[] = {'A', 'B', 'C', 'D', 'F'};
//   char name[] = "BRO CODE";

//   for (int i = 0; i < sizeof(numbers) / sizeof(numbers[0]); i++) {
//     printf("%d ", numbers[i]);
//   }

//   return 0;
// }

// int main(){

//   int scores[5] = {0};

//   for(int i = 0; i < 5; i++){
//     printf("Enter a score: ");
//     scanf("%d", &scores[i]);
//   }

//   for(int i = 0; i < 5; i++){
//     printf("%d ", scores[i]);
//   }
//   return 0;
// }

// int main() {

//   // 2D array = AN ARRAY WHERE EACH ELEMENT IS AN ARRAY:::::: array[][] =
//   {{},{},{},{}};

//   char numpad[][3] = {{'1', '2', '3'}, {'4', '5', '6'}, {'7', '8', '9'},
//   {'*', '0', '#'}};

//   for (int i = 0; i < 4; i++) { // rows
//     for (int j = 0; j < 3; j++){ // col
//       printf("%c ", numpad[i][j]);
//   }
//   printf("\n");
// }
//   return 0;
// }

// #include <string.h>
// int main() {

//   // EXERCIE:::::

//   char names[3][25] = {0};
//   int size = sizeof(names) / sizeof(names[0]);

//       for (int i = 0; i < size; i++) {
//         printf("Enter a name: ");
//         fgets(names[i], sizeof(names[i]), stdin);
//         names[i][strlen(names[i]) - 1] = '\0';
//       }

//       for (int i = 0; i < size;i++) {
//   printf("%s\n", names[i]);
// }

// return 0;
// }

// #include <ctype.h>
// int main() {
//   SetConsoleOutputCP(65001);
//   // QUIZ GAME::::::
//   // QUIZ GAME:::::::
//   // QUIZ GAME:::::::
//   char questions[][100] = {
//     "Which is the larest plenet in the Solar System?",
//     "What is the hottest planet?",
//     "What planet has the most moons?",
//     "Is the Earth flat?"
//   };
//   char options[][100] = {
//     "A. Jupiter\nB. Saturn\nC. Uranus\nD. Naptune",
//     "A. Mercury\nB. Venus\nC. Earth\nD. Mars",
//     "A. Earth\nb. Mars\nC. jupiter\nD. Saturn",
//     "A. yes\nB. No\nC. Maybe\nD. Sometimes"
//   };
//   char answers[] = {'A', 'B', 'D', 'B'};
//   int questionCount = sizeof(questions) / sizeof(questions[0]);
//   char guess = '\0';
//   int score = 0;
//   printf("    *** :::QUIZE GAME::: ***\n");
//   for(int i = 0; i < questionCount; i++){
//     printf("\n%s\n", questions[i]);
//     printf("\n%s\n", options[i]);
//     printf("Enter your choice :: ");
//     scanf(" %c", &guess);
//     guess = toupper(guess);
//     if(guess == answers[i]){
//       printf("\n    CORRET ANSWER ☑ !\n");
//       score++;
//     }else{
//       printf("\n    IN'CORRECT ANSWER 😞 !\n");
//     }
//   }
//   printf("You Score is %d out of %d points 🙋 !", score, questionCount);
//   return 0;
// }

// #include <stdbool.h>
// int main() {
//   // ternary operator ? = SHORTHAND FOR if-else STATEMENTS
//   // (CONDITION) ? value_if_true : value_if_false;

//   // bool isOnline = false;

//   // printf("%s", (isOnline) ? "ONLINE" : "OFFLINE");
//   // int n = 9;

//   // printf("%d IS %s", n, (n % 2 == 0) ? "EVEN" : "ODD");

//   // int age = 21;
//   // printf("%s", (age >= 18) ? "ADULT" : "CHILD");

//   // int hours = 12;
//   // int minutes = 3;
//   // char *meridiem = (hours < 12) ? "AM" : "PM";

//   // printf("%02d:%02d %s", hours, minutes, meridiem);

//   return 0;
// }

// // typedef int num;
// // typedef char String[50];
// // typedef char Initials[3];
// int main() {

//   // typedef = RESERVED KEYWORD THAT GIVES AM EXISTING DATATYPE A "NICKNAME"
//   // HELPS SIMPLIFY COMPLES TYPES AND IMPROVES CODE READABILITY typedef
//   // existing_type new_name;:::::::

//   // num x = 3;
//   // num y = 4;
//   // num z = x + y;
//   // printf("%d", z);

//   // String name = "BRO CODE";
//   // printf("%s", name);

//   // Initials user1 = "BC";
//   // Initials user2 = "SS";
//   // Initials user3 = "PS";
//   // Initials user4 = "ST";
//   // printf("%s\n", user1);
//   // printf("%s\n", user2);
//   // printf("%s\n", user3);
//   // printf("%s\n", user4);

//   return 0;
// }

// enum Day {
//   SUNDAY = 1,
//   MONDAY = 2,
//   TUESDAY = 3,
//   WEDNESDAY = 4,
//   THURSDAY = 5,
//   FRIDAY = 6,
//   SATURDAY = 7,
// };

// typedef enum { SUCCESS, FAILURE, PENDING } Status;
// void connectStatus(Status status);
// int main() {
//   // enum = A USER-DEFINED DATA TYPE THAT CONSISTS OF A SET NAMED INTEGER
//   // CONSTANTS. BENFIT : REPLACEES NUMBERS WITH RADABLE NAMES.::::::
//   // enum Day today = TUESDAY;
//   // if (today == SUNDAY || today == SATURDAY) {
//   //   printf("It's the weekend!");
//   // } else {
//   //   printf("it's the weekday!");
//   // }
//   Status status = PENDING;
//   connectStatus(status);
//   return 0;
// }
// void connectStatus(Status status) {
//   switch (status) {
//   case SUCCESS:
//     printf("Connection was Successful!\n");
//     break;
//   case FAILURE:
//     printf("Could not Connect!\n");
//     break;
//   case PENDING:
//     printf("Still Connecting....!\n");
//     break;
//   }
// }

// #include <stdbool.h>
// #include <string.h>
// typedef struct {
//   char name[50];
//   int age;
//   float gpa;
//   bool isFullTime;
// } Student;
// void printStudent(Student student);
// int main() {
//   // struct = A CUSTOM CONTAINER THAT HOLDS MULTIPLE PIECES OF RELATED
//   // INFORMATION. SIMILAR TO OBJECTS IN OTHER LANGUAGES::::::
//   Student student1 = {"Spongebob", 30, 2.5, true};
//   Student student2 = {"Zaibi", 36, 1.5, false};
//   Student student3 = {"Johnson", 19, 3.1, true};
//   ////adding values after initialing::
//   // Student student4 = {0};
//   // strcpy(student4.name, "Sandy");
//   // student4.age = 27;
//   // student4.gpa = 3.3;
//   // student4.isFullTime = true;
//   // strncpy(student4.name, "Sandy", 4);

//   printStudent(student1);
//   printStudent(student2);
//   printStudent(student3);
//   // printStudent(student4);
//   return 0;
// }

// void printStudent(Student student) {
//   printf("Name: %s\n", student.name);
//   printf("Age: %d\n", student.age);
//   printf("GPA: %.2f\n", student.gpa);
//   printf("FULL-TIME: %s\n", (student.isFullTime) ? "Yes" : "No");
//   printf("\n");
// }

// typedef struct {
//   char model[25];
//   int year;
//   int price;
// } Car;
// int main() {
//   // array of structs = ARRAY WHERE EACH ELEMENT CONTAINS A STRUCT {} . HELPS
//   // ORGANIZE AND GROUPS TOGETHER RELATED DATA .

//   Car cars[] = {{"Mustang", 2025, 32000},
//                 {"Corvette", 2026, 68000},
//                 {"Challenger", 2024, 29000}};
//   int number = sizeof(cars) / sizeof(cars[0]);
//   for (int i = 0; i < number; i++) {
//     printf("%s %d $%d\n", cars[i].model, cars[i].year, cars[i].price);
//   }
//   return 0;
// }

// // void birthday(int* age) ;
// // int main() {
// //   // pointer = A VARIABLE THAT STORES THE MEMORY ADDRESS OF ANOTHER
// VARIABLE.
// //   // benfit: THEY HELP AVOID WASATING MEMORYBY ALLOWING YOU TO PASSTHE
// //   ADDRESS
// //   // OF A LARGE DATA STRUCTURE INSTEAD OF CPOYING THE ENTIRE DATA:::::::
// int
// //   age
// //   // = 25;
// //   ////finidng the memory address:
// //   // printf("%p", &age);

// //   int age = 25;
// //   birthday(&age);
// //   printf("You are %d years old", age);
// //   return 0;
// // }
// // void birthday(int* age){
// //   // pass by value::
// //   // we need to pass by reference::
// //   (*age)++;
// // }

// int main(){
//   // WRITE A FILE:::::
//   // WRITE A FILE:::::
//   // WRITE A FILE:::::

//   FILE *pfile = fopen("C:\\Users\\Public\\Desktop\\output.txt", "w");
//   char text[] = "BOOTY BOOTY BOOTY\nROCKIN ' EVERYWHERE!";
//   if(pfile == NULL){
//     printf("Error opening file.\n");
//     return 1;
//   }
//   fprintf(pfile, "%s", text);
//   printf("FILE WAAS WRITTE SUCCESSFULLY! ");
//   fclose(pfile);
//   return 0;
// }

// int main() {
//   /// READ A FILE :::::
//   /// READ A FILE :::::
//   /// READ A FILE :::::

//   FILE *pFile = fopen("C:\\Users\\zaibhi\\Desktop\\input.txt", "r");
//   char buffer[1024] = {0};
//   if (pFile == NULL) {
//     printf("COULD NOT OPEN FILE !");
//     return 1;
//   }
//   while(fgets(buffer, sizeof(buffer), pFile) != NULL){
//     printf("%s", buffer);
//   }
//   fclose(pFile);
//   return 0;
// }

// int main(){
//   // malloc() = A FUNCTION IN C THAT DYNAMICALLY ALOCATESA SPEECIFIED NUMBER
//   OF BYTES IN MEMORY int number = 0; printf("Enter the number of grades: ");
//   scanf("%d", &number);
//   char *grades =  malloc(number * sizeof(char));
//   if(grades == NULL){
//     printf("MEMORY ALLLOCATION FAILED!\n");
//     return 1;
//   }
//   for (int i = 0; i < number; i++) {
//     printf("Enter grade #%d: ", i + 1);
//     scanf(" %c", &grades[i]);
//   }
//   for(int i = 0; i < number; i++){
//     printf("%c ", grades[i]);
//   }
//   free(grades); // returning "RENTED" space back to the OS
//   grades = NULL; // avoids dangling pointers

//   return 0;

// }

// #include <stdlib.h>
// #include <stdio.h>
// int main(){
//   // calloc() = Contiguous allocation.
//   // ALLOCATES MEMORY DYNAMICALLY AND SETS ALL ALLOCATED BYTES TO 0.
//   // malloc() IS FASTER, BUT calloc() LEADS TO LESS BUGS.
//   //  calloc(#, size)
//   //  malloc(bytes)
//   int number = 0;
//   printf("Enter the number of players: ");
//   scanf("%d", &number);
//   int *scores  = calloc(number, sizeof(int));
//   if(scores == NULL) {
//     printf("MEMORY ALLOCATION FAILED !\n");
//     return 1;
//   }
//   for (int i = 0; i < number; i++) {
//     printf("Enter scoire #%d: ", i + 1);
//     scanf("%d", &scores[i]);
//   }
//   for(int i = 0; i < number; i++){
//     printf("%d ", scores[i]);
//   }
//   free(scores);
//   scores = NULL;
//   return 0;
// }

// #include <stdio.h>
// #include <stdlib.h>
// int main(){
//   //// realloc() = REALLOCATION.
//   // RESIZE PREVIOUSLY ALLOCATED MEMORY.
//   // realloc(ptr, bytes); ::::::
//   int number  = 0;
//   printf("Enter the number of prices: ");
//   scanf("%d", &number);
//   float *prices = malloc(number * sizeof(float));
//   if(prices == NULL){
//     printf("MEMORY ALLOCATION FAILED !\n");
//     return 1;
//   }
//   for(int i = 0; i < number; i++){
//     printf("Enter prices %d: ",  i + 1);
//     scanf("%f", &prices[i]);
//   }
//   int new_num = 0;
//   printf("Enter a new number of prices: ");
//   scanf("%d", &new_num);
//   float *temp = realloc(prices, new_num * sizeof(float));
//   if(temp == NULL){
//     printf("COULD NOT REALLOCATE MEMORY !\n");
//   }
//   else{
//     prices = temp;
//     temp = NULL;
//     for (int i = number; i < new_num; i++) {
//       printf("Enter prices %d: ", i + 1);
//       scanf("%f", &prices[i]);
//     }
//     for (int i = 0; i < new_num; i++) {
//       printf("\n  $%.2f ", prices[i]);
//     }
//   }
//     free(prices);
//     prices = NULL;
//     return 0;
//   }

// #include <stdbool.h>
// #include <stdio.h>
// #include <time.h>
// // #include <unistd.h>
// #include <windows.h>
// int main() {
//   //// DIGITAL CLOCK ::::
//   //// DIGITAL CLOCK ::::
//   //// DIGITAL CLOCK ::::

//   time_t rawtime = 0; // Jan 1 1970 (Epoch):
//   struct tm *pTime = NULL;
//   bool isRunning = true;
//   printf("*** DIGITAL CLOCK *** \n");
//   while (isRunning) {
//     time(&rawtime);
//     pTime = localtime(&rawtime);
//     int hours = pTime->tm_hour;
//     int minutes = pTime->tm_min;
//     int seconds = pTime->tm_sec;
//     char *ampm = "AM";
//     if(hours >= 12){
//       ampm = "PM";
//       if(hours > 12){
//         hours -= 12; // convert 13 - 23 to 1 - 11:
//       }
//     }else if(hours == 0){
//       hours = 12; // convert 00 to 12 AM
//     }
//     #ifdef _WIN32
//       system("cls");
//     #else
//       system("clear");
//     #endif
//       printf("*** DIGITAL CLOCK *** \n\n");
//       printf("     %02d:%02d:%02d %s\n", hours, minutes, seconds, ampm);
//       Sleep(1000);
//   }
//   return 0;
// }










#define _GNU_SOURCE
#include <stdio.h>
#include <sys/random.h>

int main() {
    int pure_random_num;

    // Read raw, true random bytes directly into the integer variable
    ssize_t result = getrandom(&pure_random_num, sizeof(pure_random_num), 0);

    if (result < 0) {
        perror("Failed to generate random number");
        return 1;
    }

    printf("Pure Random Number: %d\n", pure_random_num);
    return 0;
}
