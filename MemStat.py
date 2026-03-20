import getpass
import rumps
import psutil
import objc
from AppKit import (
    NSAttributedString, NSColor, NSForegroundColorAttributeName, NSObject,
    NSFont, NSFontAttributeName, NSMutableParagraphStyle, NSTextTab,
    NSParagraphStyleAttributeName, NSRightTextAlignment
)

class MenuDelegate(NSObject):
    def initWithApp_(self, app):
        self = objc.super(MenuDelegate, self).init()
        if self:
            self.app = app
        return self

    def menuWillOpen_(self, menu):
        self.app.is_menu_open = True
        self.app.update_menu_list(None)

    def menuDidClose_(self, menu):
        self.app.is_menu_open = False

class MemStatApp(rumps.App):
    def __init__(self):
        super(MemStatApp, self).__init__("MemStat", title="")
        self.total_gb = psutil.virtual_memory().total / (1024 ** 3)
        self.username = getpass.getuser()
        self.is_menu_open = False
        self.delegate_set = False
        self.update_menu_list(None)

    @rumps.timer(2)
    def update_title_timer(self, _):
        if not self.delegate_set and hasattr(self, '_nsapp'):
            try:
                self.delegate = MenuDelegate.alloc().initWithApp_(self)
                self._nsapp.nsstatusitem.menu().setDelegate_(self.delegate)
                self.delegate_set = True
                self._nsapp.nsstatusitem.button().setImage_(None)
            except Exception:
                pass

        mem = psutil.virtual_memory()
        percent = mem.percent
        
        # iStat Menus와 같이 깔끔한 원형 기호(●)로 대체 (이미지 렌더링 실패 우회)
        text = f"● {percent:.0f}%"
        try:
            if hasattr(self, '_nsapp'):
                rich_title = NSAttributedString.alloc().initWithString_(text)
                mutable_rich_title = rich_title.mutableCopy()
                
                if percent < 70:
                    color = NSColor.systemGreenColor()
                elif percent < 90:
                    color = NSColor.systemYellowColor()
                else:
                    color = NSColor.systemRedColor()
                    
                mutable_rich_title.addAttribute_value_range_(
                    NSForegroundColorAttributeName, color, (0, 1) # '●' 부분에만 색상 적용
                )
                self._nsapp.nsstatusitem.setAttributedTitle_(mutable_rich_title)
            else:
                self.title = text
        except Exception:
            self.title = text

    @rumps.timer(1)
    def active_refresh_timer(self, _):
        if self.is_menu_open:
            self.update_menu_list(None)

    def get_top_processes(self):
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'memory_info']):
            try:
                info = proc.info
                if info['username'] == self.username and info['memory_info'] is not None:
                    rss = info['memory_info'].rss / (1024 ** 2)
                    processes.append({'pid': info['pid'], 'name': info['name'], 'rss': rss})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return sorted(processes, key=lambda x: x['rss'], reverse=True)[:15]

    def create_bold_menu_item(self, text):
        item = rumps.MenuItem(text)
        attributes = {
            NSFontAttributeName: NSFont.boldSystemFontOfSize_(14)
        }
        attr_str = NSAttributedString.alloc().initWithString_attributes_(text, attributes)
        item._menuitem.setAttributedTitle_(attr_str)
        return item

    def create_system_item(self, label, value_gb):
        """Wired/Compressed/Swap 항목용 정렬 아이템"""
        # 레이블 길이 제한 없음 (짧으므로), 숫자 부분만 포맷팅
        val_str = f"{value_gb:.2f} GB"
        text = f"{label}\t{val_str}"
        item = rumps.MenuItem(text)
        
        # 1. 기본 폰트 및 탭 설정
        sys_font = NSFont.menuBarFontOfSize_(14.0)
        paragraph_style = NSMutableParagraphStyle.alloc().init()
        tab = NSTextTab.alloc().initWithTextAlignment_location_options_(NSRightTextAlignment, 240, {})
        paragraph_style.setTabStops_([tab])
        
        attributes = {
            NSFontAttributeName: sys_font,
            NSParagraphStyleAttributeName: paragraph_style
        }
        
        attr_str = NSAttributedString.alloc().initWithString_attributes_(text, attributes)
        mutable_attr_str = attr_str.mutableCopy()
        
        # 2. 숫자 부분에만 고정폭(Monospaced Digit) 적용하여 정렬 보장
        mono_font = NSFont.monospacedDigitSystemFontOfSize_weight_(14.0, 0.0)
        val_range = (len(label) + 1, len(val_str))
        mutable_attr_str.addAttribute_value_range_(NSFontAttributeName, mono_font, val_range)
        
        item._menuitem.setAttributedTitle_(mutable_attr_str)
        return item

    def create_menu_item(self, app_name, memory_mb, callback, pid, proc_name):
        """앱 리스트 정렬 아이템 (이름 자르기 및 숫자 고정폭 적용)"""
        # 앱 이름이 너무 길면 탭이 밀리는 현상을 방지하기 위해 20자로 제한하고 말줄임표 처리
        display_name = app_name
        if len(display_name) > 20:
            display_name = display_name[:19] + "…"
            
        # 숫자 부분 포맷 (예: '1015.6 MB', ' 585.4 MB') -> 소수점 앞을 맞추기 위해 공간 확보
        val_str = f"{memory_mb:>6.1f} MB"
        text = f"{display_name}\t{val_str}"
        
        item = rumps.MenuItem(text, callback=callback)
        item.pid = pid
        item.proc_name = proc_name
        
        # 1. 기본 시스템 폰트 및 탭 설정
        sys_font = NSFont.menuBarFontOfSize_(14.0)
        paragraph_style = NSMutableParagraphStyle.alloc().init()
        tab = NSTextTab.alloc().initWithTextAlignment_location_options_(NSRightTextAlignment, 240, {})
        paragraph_style.setTabStops_([tab])
        
        attributes = {
            NSFontAttributeName: sys_font,
            NSParagraphStyleAttributeName: paragraph_style
        }
        
        attr_str = NSAttributedString.alloc().initWithString_attributes_(text, attributes)
        mutable_attr_str = attr_str.mutableCopy()
        
        # 2. 숫자(메모리) 부분에만 고정폭 숫자 폰트 적용
        mono_font = NSFont.monospacedDigitSystemFontOfSize_weight_(14.0, 0.0)
        val_range = (len(display_name) + 1, len(val_str))
        mutable_attr_str.addAttribute_value_range_(NSFontAttributeName, mono_font, val_range)
        
        item._menuitem.setAttributedTitle_(mutable_attr_str)
        return item

    def update_menu_list(self, _):
        self.menu.clear()
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        used_gb = mem.used / (1024**3)
        total_gb = mem.total / (1024**3)
        percent = mem.percent
        
        header_text = f"Memory: {used_gb:.1f} GB / {total_gb:.1f} GB ({percent:.0f}%)"
        self.menu.add(self.create_bold_menu_item(header_text))
        self.menu.add(rumps.separator)
        
        wired = getattr(mem, 'wired', 0) / (1024**3)
        compressed = getattr(mem, 'compressed', 0) / (1024**3)
        swap_used = swap.used / (1024**3)
        
        self.menu.add(self.create_system_item("Wired:", wired))
        self.menu.add(self.create_system_item("Compressed:", compressed))
        self.menu.add(self.create_system_item("Swap Used:", swap_used))
        
        self.menu.add(rumps.separator)
        # 행 전체가 클릭 영역이므로 클릭 시 종료됨을 명시
        self.menu.add(self.create_bold_menu_item("Top Processes (Click Row to Terminate)"))

        top_procs = self.get_top_processes()
        for proc in top_procs:
            self.menu.add(self.create_menu_item(
                app_name=proc['name'],
                memory_mb=proc['rss'],
                callback=self.terminate_app,
                pid=proc['pid'],
                proc_name=proc['name']
            ))

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Terminate MemStat", callback=rumps.quit_application))

    def terminate_app(self, sender):
        try:
            if not getattr(sender, 'pid', None): return
            pid = sender.pid
            name = sender.proc_name
            response = rumps.alert(
                title="Terminate Process",
                message=f"Are you sure you want to terminate '{name}' (PID: {pid})?",
                ok="Terminate",
                cancel="Cancel"
            )
            if response == 1:
                psutil.Process(pid).terminate()
                rumps.notification("MemStat", "Terminated", f"'{name}' has been closed.")
                self.update_menu_list(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            rumps.alert("Error", str(e))

if __name__ == "__main__":
    MemStatApp().run()