# Vietsub AI Studio

[![Kiểm tra Windows](https://github.com/lythusai1982-web/manh-tool/actions/workflows/windows-test.yml/badge.svg)](https://github.com/lythusai1982-web/manh-tool/actions/workflows/windows-test.yml)

Tool Windows tự nhận diện lời nói trong video, dịch sang tiếng Việt, tạo phụ đề và lồng giọng Việt đồng bộ.

## Tính năng

- Nhận diện tự động nhiều ngôn ngữ bằng Faster-Whisper.
- Dịch nội dung sang tiếng Việt theo từng đoạn thời gian.
- Xuất tệp `.srt` và có thể chèn Vietsub trực tiếp lên video.
- Giọng Việt tự nhiên: nữ Hoài My hoặc nam Nam Minh.
- Tự căn giọng đọc theo từng câu; câu dài được tăng tốc nhẹ để giảm lệch tiếng.
- Tùy chọn giữ tiếng gốc nhỏ phía sau, giúp video tự nhiên hơn.
- Xuất MP4 H.264/AAC, dễ mở trên Windows, điện thoại và phần mềm dựng.
- Hỗ trợ MP4, MKV, MOV, AVI, WEBM và M4V.

## Cách dùng trên Windows

1. Giải nén toàn bộ thư mục.
2. Nhấp đúp `SUA_LOI_VA_MO_TOOL.bat`. Trình cài đặt sẽ kiểm tra **Python 3.12**, cài Microsoft Visual C++ Runtime và dùng bộ thư viện ổn định.
3. Chọn video, giọng đọc, độ chính xác rồi bấm **BẮT ĐẦU DỊCH**.

Sau lần cài đầu tiên, có thể dùng `Chay_Nhanh.bat` để mở nhanh.

## Nếu tool không mở

1. Chạy `SUA_LOI_VA_MO_TOOL.bat` và chờ đủ năm bước.
2. Nếu vẫn chưa mở, chạy `Kiem_Tra_Loi.bat`.
3. Tool sẽ tạo `loi_khoi_dong.txt` hoặc `nhat_ky_cai_dat.txt` thay vì tự tắt mà không báo nguyên nhân.

Lỗi trong bản trước đến từ `CTranslate2` trên Windows. Bản này tự cài Microsoft Visual C++ Runtime theo yêu cầu chính thức của CTranslate2 và khóa bộ `faster-whisper 1.1.1` + `CTranslate2 4.6.0` để tránh bản cập nhật mới gây lỗi DLL.

Lỗi `No module named 'pkg_resources'` được xử lý bằng cách khóa `setuptools 80.9.0`, là phiên bản vẫn cung cấp thành phần mà `CTranslate2 4.6.0` cần.

Môi trường AI được đặt tại `C:\Users\Public\VietsubAI_Runtime`, tránh lỗi DLL khi tên tài khoản Windows hoặc thư mục tải xuống có dấu tiếng Việt, khoảng trắng hay `(1)`.

Lần đầu chạy cần Internet và có thể lâu hơn vì công cụ tải mô hình nhận diện. Những lần sau mô hình được dùng lại từ máy.

## Chọn mô hình

- `base`: nhanh, phù hợp máy yếu, độ chính xác vừa.
- `small`: cân bằng tốc độ và chất lượng, nên dùng mặc định.
- `medium`: chính xác hơn nhưng cần máy mạnh và nhiều RAM.

## Kết quả

Trong thư mục xuất sẽ có:

- `Tên video - Tiếng Việt.mp4`: video hoàn chỉnh.
- `Tên video - Vietsub.srt`: phụ đề tiếng Việt để chỉnh sửa hoặc đăng YouTube.

## Lưu ý quan trọng

- Công cụ cần Internet khi dịch và tạo giọng đọc.
- Chất lượng phụ thuộc độ rõ của âm thanh gốc, tiếng ồn, giọng địa phương và số người nói cùng lúc.
- Công cụ không sao chép giọng thật của nhân vật; nó sử dụng giọng đọc tiếng Việt tổng hợp.
- Chỉ xử lý video bạn sở hữu hoặc được phép sử dụng. Không dùng để đăng lại nội dung có bản quyền khi chưa được cho phép.
