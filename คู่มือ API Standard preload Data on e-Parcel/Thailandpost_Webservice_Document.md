# คู่มือ Thailandpost Webservice Document (API Standard preload Data on e-Parcel)

**ข้อมูลพื้นฐาน:**
- **URL หลัก:** `https://r_dservice.thailandpost.com/`
- **Authentication:** Basic Authentication [Username/Password]
- **Content-Type:** `application/json`

---

## 1. Management (การจัดการร้านค้าและคลังสินค้า)
- **สร้าง Merchant หรือสาขา (createMerchant):** `PUT /webservice/addMerchant`
- **อัปเดต Merchant หรือสาขา (updateMerchant):** `POST /webservice/updateMerchant`
- **ดูรายละเอียด Merchant (getMerchant):** `GET /webservice/getMerchant`
- **สร้างคลังสินค้า (createStore):** `PUT /webservice/addStoreLocation`

## 2. Orders (การสร้างและจัดการออเดอร์)
- **สร้างรายการ Order เดี่ยว (createOrder):** `POST /webservice/addItem`
- **สร้างรายการ Orders หลายรายการ (createOrders):** `POST /webservice/addItems`
- **อัปเดตข้อมูล Order (updateOrder):** `POST /webservice/updateItem`
- **ยกเลิกรายการ Order (cancelOrder):** `POST /webservice/cancelOrder`

## 3. PrePrint (การพิมพ์เอกสาร)
- **พิมพ์ใบรับฝากสิ่งของ (DepositPDF):** `GET /webservice/DepositPDF?manifestNo=:manifestNo`
- **พิมพ์ใบปะหน้ากล่องสินค้า (LabelPDF):** `GET /webservice/LabelPDF?barcode=:barcode&urlLogo=:urlLogo`

## 4. Reports & Status (การตรวจสอบสถานะและรายงาน)
- **เช็คสถานะพัสดุ (getStatus):** `GET /webservice/getStatus` (ข้อมูลสถานะทั้งหมด)
- **เช็คประวัติสถานะพัสดุ (getHistoryStatus):** `GET /webservice/getHistoryStatus?barcode=:barcode`
- **ค้นหาจากบาร์โค้ด (getOrderByBarcode):** `GET /webservice/getOrderByBarcode?barcode=:barcode`
- **ค้นหาหลายบาร์โค้ด (getOrderByBarcodes):** `POST /webservice/getOrderByBarcodes` (คั่นด้วย `,`)
- **รายงานสินค้าจัดส่งสำเร็จ (getAllOrderDelivered):** `GET /webservice/getAllOrderDelivered?date=:date`
- **รายงานสินค้าส่งคืน (getAllOrderReverse):** `GET /webservice/getAllOrderReverse?date=:date`
- **ตรวจสอบตามช่วงเวลา (getOrderByDurationTime):** `POST /webservice/getOrderByDurationTime`
- **รายงานการจัดส่งรายวัน (reportJSON):** `GET /webservice/reportJSON?date=:date`

## 5. Rates (การคำนวณราคา)
- **เช็คราคาสินค้าตามใบรับฝาก (getRateByManifest):** `POST /webservice/getRateByManifest`
- **เช็คราคาจากน้ำหนักและประเภท (getRatePriceByWeight):** `POST /webservice/getRatePriceByWeight`
- **เช็คราคาตาม Zone (getRatePriceZoneByWeight):** `POST /webservice/getRatePriceZoneByWeight`

---

## 📌 โครงสร้าง Error Code ที่พบบ่อย:
- `000` : Success
- `001` : Invalid Username and Password
- `002` : Invalid Input
- `016` : Weight Over!
- `018` : Duplicate Barcode
- `031` : Create Order Fail!

---
*เอกสารนี้ถูกจัดทำขึ้นจากข้อมูลอ้างอิงล่าสุดของเว็บ r_dservice.thailandpost.com*
