# Windows 11 환경 pgModeler 소스 빌드 및 설치 가이드

Windows 환경에서 Visual Studio나 무거운 상용 Qt 설치 프로그램 없이, 패키지 매니저(MSYS2)만을 이용해 최신 pgModeler 소스 코드를 빌드하고 `C:\Program Files`에 정식 설치하는 단계별 매뉴얼입니다.

`data-modeling` 스킬이 만들어 주는 `03_model.dbm` 파일을 열어 보려면 pgModeler가 필요합니다. 이 문서는 그 설치 과정을 정리한 것입니다.

---

## 1. 사전 준비 (MSYS2 설치)

1. [MSYS2 공식 웹사이트](https://www.msys2.org/)에 접속하여 Windows용 설치 파일(`.exe`)을 다운로드합니다.
2. 기본 경로(`C:\msys64`)에 설치를 완료합니다.

---

## 2. 개발 도구 및 의존성 패키지 설치

1. Windows 시작 메뉴에서 **`MSYS2 MINGW64`**를 찾아 **일반 사용자 권한**으로 실행합니다.
   *(반드시 보라색/파란색 아이콘의 **MINGW64** 터미널을 사용해야 합니다. `MSYS`나 `UCRT64` 터미널이 아닙니다.)*
2. 다음 명령어를 실행하여 빌드 도구와 필수 라이브러리들을 설치합니다:

```bash
pacman -S --needed --noconfirm git \
  mingw-w64-x86_64-gcc \
  mingw-w64-x86_64-clang \
  mingw-w64-x86_64-make \
  mingw-w64-x86_64-cmake \
  mingw-w64-x86_64-ninja \
  mingw-w64-x86_64-qt6-base \
  mingw-w64-x86_64-qt6-svg \
  mingw-w64-x86_64-postgresql \
  mingw-w64-x86_64-libxml2
```

---

## 3. 소스 코드 복제(Clone) 및 컴파일

1. 터미널에서 pgModeler 소스 코드를 내려받습니다:

```bash
cd ~
git clone https://github.com/pgmodeler/pgmodeler.git
cd pgmodeler
```

2. **이 가이드와 같은 버전(v2.0.0-beta1)으로 고정**합니다. 저장소는 계속 바뀌므로, 이 단계를 거쳐야 모두가 같은 코드로 빌드하게 됩니다:

```bash
# 태그 v2.0.0-beta1 로 체크아웃 (커밋 102925d1)
git checkout v2.0.0-beta1

# 확인 — 아래 해시가 102925d159e5eb7b570f09b23ef55af506b7f3d4 로 시작하면 정상
git rev-parse HEAD
```

> 태그가 없다는 오류가 나면 `git fetch --tags` 후 다시 체크아웃합니다. "detached HEAD" 안내 메시지는 정상이니 무시해도 됩니다.
> 참고: 설치 후 Help › About 의 **Build** 번호(예: `20261001`)는 *빌드한 날짜*로 찍히므로 PC마다 다릅니다. **Number** 가 `v2.0.0-beta1` 이면 같은 버전입니다.

3. 빌드 폴더를 만들고 CMake 구성 및 컴파일을 진행합니다:

```bash
mkdir -p build && cd build
```

```bash
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ..
ninja
```

> **주의:** 소스 디렉터리 내에 `pgmodeler.pro`(qmake)가 없고 `CMakeLists.txt`만 존재하는 최신 버전이므로 CMake와 Ninja를 사용해야 합니다.
> 컴파일은 PC 사양에 따라 10~30분 정도 걸립니다.

---

## 4. 프로그램 시스템 설치 (관리자 권한)

pgModeler는 컴파일 시점에 리소스(설정 파일, 스키마, UI 에셋)를 참조할 경로로 `C:\Program Files`를 하드코딩합니다. 시스템 디렉터리 쓰기 권한이 필요하므로 관리자 권한으로 설치를 완료합니다.

1. **현재 열려 있는 터미널을 닫습니다.**
2. Windows 시작 메뉴에서 `MSYS2 MINGW64`를 검색합니다.
3. 마우스 우클릭 후 **[관리자 권한으로 실행]**을 선택합니다.
4. 관리자 터미널에서 아래 명령어를 차례대로 입력하여 설치를 마칩니다:

```bash
# 빌드 경로로 이동
cd ~/pgmodeler/build

# C:/Program Files 로 바이너리 및 필수 에셋 일괄 설치
ninja install

# 실행에 필요한 Qt DLL 자동 수집 및 배포
windeployqt6 "/c/Program Files/pgmodeler.exe"

# PostgreSQL 및 필수 시스템 라이브러리 DLL 복사
cp /mingw64/bin/libpq*.dll     "/c/Program Files/"
cp /mingw64/bin/libxml2*.dll   "/c/Program Files/"
cp /mingw64/bin/libcrypto*.dll "/c/Program Files/"
cp /mingw64/bin/libssl*.dll    "/c/Program Files/"

# 이전 실행 실패로 남아있을 수 있는 캐시/설정 데이터 초기화
rm -rf "/c/Users/$USER/AppData/Local/pgmodeler-2.0"
```

5. **Windows 시스템 환경변수(PATH)에 MinGW 경로 영구 등록 (필수)**
   PC 재시작 후 MinGW C/C++ 런타임 DLL 누락으로 프로그램 실행이 실패하는 문제를 방지하기 위해 시스템 PATH에 경로를 영구 등록합니다.
   * **PowerShell(관리자 권한)**을 열고 아래 명령어를 실행합니다:

```powershell
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "Machine") + ";C:\msys64\mingw64\bin",
    "Machine"
)
```

   * 수동 설정: `Win + R` → `sysdm.cpl` → [고급] → [환경 변수] → [시스템 변수]의 `Path`에 `C:\msys64\mingw64\bin` 추가
   * 등록 후에는 열려 있던 터미널·탐색기를 닫고 다시 열어야 적용됩니다.

---

## 5. 실행 및 바로가기 등록

설치가 정상적으로 완료되었습니다.

* **실행 파일 위치:** `C:\Program Files\pgmodeler.exe`
* 윈도우 탐색기에서 위 경로로 이동한 뒤 `pgmodeler.exe`를 우클릭하여 **[바탕화면에 바로가기 만들기]** 또는 **[시작 화면에 고정]**을 해두고 사용하시면 됩니다.

---

## 6. 스킬 산출물(.dbm) 열어 보기

1. pgModeler 실행 → **File › Load model** → 스킬이 만든 `03_model.dbm` 선택
2. 테이블·컬럼·관계선을 **한글 논리명**으로 보려면 상단 **Show** 메뉴(또는 **Settings › General**)의 **object aliases** 토글을 켭니다. 끄면 영문 물리명으로 돌아옵니다.
3. 열 때 *버전이 맞지 않는다*는 오류가 나면, `.dbm` 파일 첫 줄의 `pgmodeler-ver="1.1.0"` 값을 설치된 pgModeler 버전(Help › About 에서 확인) 이하로 고친 뒤 다시 엽니다.
4. 테이블 배치가 겹쳐 보이면 **Edit › Arrange objects** 로 자동 정렬하면 됩니다.

---

## 문제가 생겼을 때

| 증상 | 확인할 것 |
|---|---|
| `cmake` 또는 `ninja` 명령을 찾을 수 없음 | MINGW64 터미널인지 확인 (프롬프트에 `MINGW64` 표시). 2단계 pacman 설치를 다시 실행 |
| `ninja install` 권한 오류 | 4단계처럼 **관리자 권한**으로 연 MINGW64 터미널인지 확인 |
| 실행 시 `Qt6Core.dll` 등 DLL 없음 오류 | `windeployqt6` 가 정상 실행됐는지 확인하고 4단계 DLL 복사 명령을 다시 실행 |
| PC 재부팅 후 실행 실패 / `libgcc`·`libstdc++`·`libwinpthread` 등 DLL 누락 오류 | 4단계 5번의 **시스템 환경변수(PATH)에 `C:\msys64\mingw64\bin` 등록**이 적용됐는지 확인 (PowerShell에서 `$env:Path -split ';'` 로 확인) |
| 실행은 되는데 빈 화면/설정 오류 | 4단계 4번의 캐시 초기화(`rm -rf …/pgmodeler-2.0`) 후 재실행 |
