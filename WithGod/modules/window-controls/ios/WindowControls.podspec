Pod::Spec.new do |s|
  s.name           = 'WindowControls'
  s.version        = '1.0.0'
  s.summary        = 'iPadOS 26 window controls insets bridge'
  s.description    = 'Reports the area taken by the iPadOS 26 window controls so headers can avoid them.'
  s.author         = 'WithGod'
  s.homepage       = 'https://mincha.co.kr'
  s.platforms      = { :ios => '15.1' }
  s.source         = { git: '' }
  s.license        = { :type => 'MIT' }
  s.static_framework = true
  s.dependency 'ExpoModulesCore'
  s.source_files = "**/*.swift"
end
