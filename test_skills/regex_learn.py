import re

text1 = "Invoice number is 12345"
text2 = "Order: ABC999"
text3 = "No numbers here"

# Write code to print the first number from each text
# If no number found, print "no number found"


match_text1 = re.search(r'\d+',text1)
if match_text1:
    print(match_text1.group())
else:
    print('no number found')

match_text2 = re.search(r'\d+', text2)
if match_text2:
    print(match_text2.group())
else:
    print('no number found')

match_text3 = re.search(r'\d+',text3)
if match_text3:
    print(match_text3.group())
else:
    print('no number found')