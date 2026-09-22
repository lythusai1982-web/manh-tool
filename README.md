# Vietsub AI Studio — bản ngoại tuyến

[![Kiểm tra Windows](https://github.com/lythusai1982-web/manh-tool/actions/workflows/windows-test.yml/badge.svg)](https://github.com/lythusai1982-web/manh-tool/actions/workflows/windows-test.yml)

Tool Windows nhận diện lời nói trong video, dịch sang tiếng Việt, tạo phụ đề và lồng giọng Việt đồng bộ. Phần dịch và giọng đọc chạy trực tiếp trên máy nên không bị lỗi `Too many requests`, không cần API key và không giới hạn số lần sử dụng.

## Điểm mới

- Bỏ hoàn toàn Google Translate và Edge TTS khỏi quá trình xử lý.
- Dịch cục bộ bằng các gói Argos/CTranslate2; tự tìm tuyến dịch trực tiếp hoặc qua tiếng Anh.
- Đọc tiếng Việt cục bộ bằng Piper với giọng `vi_VN-vais1000-medium`.
- Mô hình chỉ tải ở lần sử dụng đầu tiên, sau đó được lưu và dùng lại.
- Có thể dịch và tạo giọng khi không có Internet sau khi đủ mô hình đã được tải.
- Tải mô hình có tệp tạm, kiểm tra ZIP an toàn và chỉ cài khi dữ liệu hợp lệ.
- Hỗ trợ hủy trong lúc tải hoặc xử lý, không để giao diện bị treo.

## Tính năng

- Tự nhận diện nhiều ngôn ngữ bằng Faster-Whisper.
- Tạo `.srt` UTF-8 và chèn Vietsub trực tiếp vào video.
- Tự căn giọng đọc theo từng câu; tăng tốc nhẹ câu dài để giảm lệch tiếng.
- Tùy chọn giữ nhỏ tiếng gốc phía sau giọng Việt.
- Xuất MP4 H.264/AAC, dễ mở trên Windows, điện thoại và phần mềm dựng.
- Nhận MP4, MKV, MOV, AVI, WEBM và M4V.

## Cài và mở trên Windows

1. Giải nén toàn bộ tệp ZIP ra một thư mục.
2. Nhấp đúp `SUA_LOI_VA_MO_TOOL.bat`.
3. Chờ đủ 5 bước. Trình cài đặt tự kiểm tra Python 3.12, Microsoft Visual C++ Runtime và các thư viện cần thiết.
4. Chọn video, chế độ đầu ra, độ chính xác rồi bấm **BẮT ĐẦU DỊCH**.

Từ lần sau, dùng `Chay_Nhanh.bat` để mở nhanh.

## Internet và mô hình

Lần đầu tiên vẫn cần Internet để tải:

- mô hình Faster-Whisper đã chọn (`base`, `small` hoặc `medium`);
- gói dịch cho ngôn ngữ của video và tiếng Việt;
- giọng Việt Piper Vais1000 (khoảng 63 MB) nếu chọn lồng tiếng.

Ví dụ, video tiếng Trung thường cần hai gói `zh → en` và `en → vi`. Sau khi tải xong, tool tái sử dụng chúng tại `C:\Users\Public\VietsubAI_Runtime\models` và không gửi từng câu lên máy chủ.

Khả năng dịch phụ thuộc vào các cặp ngôn ngữ đang có trong danh mục Argos. Tool hỗ trợ nhiều ngôn ngữ phổ biến và tự đi qua ngôn ngữ trung gian, nhưng không thể bảo đảm mọi ngôn ngữ hiếm. Nếu chưa có tuyến dịch, tool sẽ báo rõ thay vì tạo phụ đề sai.

## Chọn độ chính xác

- `base`: nhanh nhất, hợp máy yếu, độ chính xác vừa.
- `small`: cân bằng tốc độ và chất lượng, là lựa chọn mặc định.
- `medium`: chính xác hơn nhưng cần máy mạnh và nhiều RAM.

## Kết quả

Thư mục xuất có:

- `Tên video - Tiếng Việt.mp4`: video hoàn chỉnh.
- `Tên video - Vietsub.srt`: phụ đề tiếng Việt để chỉnh sửa hoặc tải lên nền tảng video.

## Nếu tool không mở

1. Chạy lại `SUA_LOI_VA_MO_TOOL.bat` và chờ đủ năm bước.
2. Nếu vẫn chưa mở, chạy `Kiem_Tra_Loi.bat`.
3. Xem `loi_khoi_dong.txt` hoặc `nhat_ky_cai_dat.txt` trong thư mục tool.

Môi trường Python được đặt tại `C:\Users\Public\VietsubAI_Runtime` để tránh lỗi DLL khi tên tài khoản hoặc thư mục tải xuống có dấu, khoảng trắng hay `(1)`. Bộ `faster-whisper 1.1.1`, `CTranslate2 4.6.0`, `NumPy 1.x` và `setuptools 80.9.0` được khóa để giữ tương thích với Python 3.12 trên Windows.

## Lưu ý

- Tốc độ phụ thuộc CPU, RAM, độ dài video và mô hình nhận diện đã chọn.
- Chất lượng phụ thuộc độ rõ âm thanh gốc, tiếng ồn, giọng địa phương và số người nói cùng lúc.
- Tool dùng giọng tổng hợp, không sao chép giọng thật của nhân vật.
- Chỉ xử lý video bạn sở hữu hoặc được phép sử dụng.
- Xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) để biết nguồn và giấy phép của thành phần/mô hình.
