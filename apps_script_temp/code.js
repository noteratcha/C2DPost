function doGet(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("vertion");
  
  // นับจำนวนครั้งที่ C1
  var rangeC1 = sheet.getRange("C1");
  var count = rangeC1.getValue();
  
  if (isNaN(count) || count === "") {
    count = 0;
  }
  
  count = count + 1;
  rangeC1.setValue(count);
  
  // บันทึกเวลาล่าสุดที่ D1
  var rangeD1 = sheet.getRange("D1");
  var now = new Date();
  var formattedTime = Utilities.formatDate(now, "Asia/Bangkok", "dd/MM/yyyy HH:mm:ss");
  rangeD1.setValue(formattedTime);
  
  return ContentService.createTextOutput("Success: " + count);
}
