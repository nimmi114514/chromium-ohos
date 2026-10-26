ui::RequestKeyboardReason Textfield::GetRequestKeyboardReason() const {
  return request_keyboard_reason_;
}

display::Display Textfield::GetDisplayForClient() {
  display::Screen* screen = display::Screen::GetScreen();
  if (GetNativeView()) {
    return screen->GetDisplayNearestWindow(GetNativeView());
  }
  return screen->GetPrimaryDisplay();
}

void Textfield::SetRequestKeyboardReasonWithPointer(
    ui::EventPointerType pointer_type) {
  switch (pointer_type) {
    case ui::EventPointerType::kMouse:
      request_keyboard_reason_ =
          ui::RequestKeyboardReason::REQUEST_KEYBOARD_REASON_MOUSE;
      break;
    case ui::EventPointerType::kTouch:
      request_keyboard_reason_ =
          ui::RequestKeyboardReason::REQUEST_KEYBOARD_REASON_TOUCH;
      break;
    default:
      request_keyboard_reason_ =
          ui::RequestKeyboardReason::REQUEST_KEYBOARD_REASON_OTHER;
      break;
  }
}

void MenuController::OnWidgetBoundsChanged(Widget* widget,
                                           const gfx::Rect& new_bounds) {
  DCHECK_EQ(owner_, widget);
  if (widget->IsVisible()) {
    Cancel(ExitType::kAll);
  }
}
