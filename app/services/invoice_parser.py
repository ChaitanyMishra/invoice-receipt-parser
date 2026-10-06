import re

t = """
Tax Invoice/Bill of Supply/Cash Memo\n(Original for Recipient)\nSignature valid\nDigitally signed by DS AMAZON SELLER SERVICES PRIVATE LIMITED 6\nDate: 2025.12.28 18:18:40 UTC\nReason: Invoice\nSold By : Billing Address :\nAmazon Seller Services Private Limited Chetan\n*#26/1, Brigade Gateway, 8th Floor., Dr Chetan\nRajkumar Road, Malleshwaram West 35/79 Bangali Mohal, Kanpur, Dwarikadhish Road,\nBangalore, Karnataka – 560055 bengali mohal, shiwala\nIN Kanpur, UTTAR PRADESH, 208001\nIN\nState/UT Code:09\nPAN No:AAICA3918J\nGST Registration No:29AAICA3918J1ZE\nShipping Address :\nCIN No:U51900KA2010PTC053234\nChetan\nDynamic QR Code:\nChetan\n35/79 Bangali Mohal, Kanpur, Dwarikadhish Road,\nbengali mohal, shiwala\nKanpur, UTTAR PRADESH, 208001\nIN\nState/UT Code:09\nPlace of supply:UTTAR PRADESH\nPlace of delivery:UTTAR PRADESH\nOrder Number:406-6548532-6482720 Invoice Number :POD-26-241475108\nOrder Date:28.12.2025 Invoice Details :UP-LKO1-1044-2526\nInvoice Date :28.12.2025\nSl. No Description Unit Price Qty Net Amount Tax Rate Tax Type Tax Amount Total Amount\n1 Cash/Pay on Delivery fee: ₹5.93 ₹5.93 18% IGST ₹1.07 ₹7.00\nTOTAL: ₹1.07 ₹7.00\nAmount in Words:\nSeven only\nFor Amazon Seller Services Private Limited:\nAuthorized Signatory\n(1) Service Accounting Code: 998599\nWhether tax is payable under reverse charge - No\nPlease note that this invoice is not a demand for payment\nRegd Office: Amazon Seller Services Private Limited\n8th Floor, Brigade World Trade Center\nDr Raj Kumar Road, Malleshwaram(West)\nTelephone: +91 89 33420300\nFax: +91 80 30625685\nEmail: customer-service@amazon.in\nAmazon.in - Amazon Seller Services Private Limited\n*ASSPL-Amazon Seller Services Pvt. Ltd., ARIPL-Amazon Retail India Pvt. Ltd. (only where Amazon Retail India Pvt. Ltd. fulfillment center is co-located)\nCustomers desirous of availing input GST credit are requested to create a Business account and purchase on Amazon.in/business from Business eligible offers\nPage 1 of 1\nTax Invoice/Bill of Supply/Cash Memo\n(Original for Recipient)\nSold By : Billing Address :\nCLICKTECH RETAIL PRIVATE LIMITED Chetan\n*Khasra numbers:444(P),445(P),459(P), 35/79 Bangali Mohal, Kanpur, Dwarikadhish Road,\n460,461,462,463,464, bengali mohal, shiwala\n465,466,467,468,469,470,471,472,473,474,,, Kanpur, UTTAR PRADESH, 208001\n75(P),476,477,478, 479,480, IN\n481,482,483(P),491,492,493(P) Village - State/UT Code:09\nBhaukapur,\nLucknow, Uttar Pradesh, 226401\nIN Shipping Address :\nChetan\nChetan\nPAN No:AAJCC9783E 35/79 Bangali Mohal, Kanpur, Dwarikadhish Road,\nGST Registration No:09AAJCC9783E1Z5 bengali mohal, shiwala\nKanpur, UTTAR PRADESH, 208001\nDynamic QR Code:\nIN\nState/UT Code:09\nPlace of supply:UTTAR PRADESH\nPlace of delivery:UTTAR PRADESH\nOrder Number:406-6548532-6482720 Invoice Number :LKO1-3317313\nOrder Date:28.12.2025 Invoice Details :UP-LKO1-297683823-2526\nInvoice Date :28.12.2025\nSl. Unit Net Tax Tax Tax Total\nDescription Qty\nNo Price AmountRateType AmountAmount\n1 Boat 2025 Launch Bassheads 213L, 10mm Drivers, Signature Sound,\nin-Line Microphone, Integrated Controls, 3.5mm L-Shaped Connector\n& 120cm Braided Cable Wired Earphones with Mic (Active Grey) | ₹295.76 1 ₹295.76 9% CGST ₹26.62 ₹349.00\nB0FM38BDD1 ( B0FM38BDD1 )\nHSN:85183020\n9% SGST ₹26.62\nShipping Charges ₹66.94 ₹66.94 9% CGST ₹6.03 ₹79.00\n9% SGST ₹6.03\nTOTAL: ₹65.30₹428.00\nAmount in Words:\nFour Hundred Twenty-eight only\nFor CLICKTECH RETAIL PRIVATE LIMITED:\nAuthorized Signatory\nWhether tax is payable under reverse charge - No\n*ASSPL-Amazon Seller Services Pvt. Ltd., ARIPL-Amazon Retail India Pvt. Ltd. (only where Amazon Retail India Pvt. Ltd. fulfillment center is co-located)\nCustomers desirous of availing input GST credit are requested to create a Business account and purchase on Amazon.in/business from Business eligible offers\nPlease note that this invoice is not a demand for payment\nPage 1 of 
"""


def parse_invoice_text(text: str) -> dict:
    parsed_text = {}
    invoice_number = re.search(r"Invoice Number\s*:\s*(\S+)", text)
    invoice_date = re.search(r"Invoice Date\s*:\s*(\d{2}\.\d{2}\.\d{4})", text)
    gst_in = re.search(r"GST Registration No\s*:\s*(\S+)", text)
    order_number = re.search(r"Order Number\s*:\s*(\d{3}-\d{7}-\d{7})", text)
    total = re.search(r"TOTAL\s*:\s*₹\s*[\S.,]+\s*₹\s*([\S.,]+)", text)
    tax_amount = re.search(r"TOTAL\s*:\s*₹\s*([\S.,]+)\s*₹", text)
    vendor_name= re.search(r"(?m)^For\s+(.+?)\s*:\s*$", text)
    
    
    if invoice_number:
        parsed_text['invoice_number'] = invoice_number.group(1)
    else:
        parsed_text['invoice_number'] = None
    if invoice_date:
        parsed_text['date'] = invoice_date.group(1)
    else:
        parsed_text['date'] = None
    if gst_in:
        parsed_text['gstin'] = gst_in.group(1)
    else:
        parsed_text['gstin'] = None
    if order_number:
        parsed_text['order_number'] = order_number.group(1)
    else:
        parsed_text['order_number'] = None
    if total:
        parsed_text['total'] = total.group(1)
    else:
        parsed_text['total'] = None
    if tax_amount:
        parsed_text['tax_amount']= tax_amount.group(1)
    else:
        parsed_text['tax_amount'] = None
    if vendor_name:
        parsed_text['vendor_name']=vendor_name.group(1)
    else:
        parsed_text['vendor_name'] = None   
    return parsed_text


print(parse_invoice_text(t))
