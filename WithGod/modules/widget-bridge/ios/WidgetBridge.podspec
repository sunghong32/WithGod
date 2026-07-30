Pod::Spec.new do |s|
  s.name           = 'WidgetBridge'
  s.version        = '1.0.0'
  s.summary        = 'App Group bridge for widget language sync'
  s.description    = 'Shares the in-app language override with the widget extension.'
  s.author         = 'WithGod'
  s.homepage       = 'https://mincha.co.kr'
  s.platforms      = { :ios => '15.1' }
  s.source         = { git: '' }
  s.license        = { :type => 'MIT' }
  s.static_framework = true
  s.dependency 'ExpoModulesCore'
  s.source_files = "**/*.swift"
end
