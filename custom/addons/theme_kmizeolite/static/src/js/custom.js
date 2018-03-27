
$(window).scroll(function() {    
    var scroll = $(window).scrollTop();

    if (scroll > 50) {
        $("#wrapwrap > header").addClass("header_scrolled");
    } else {
        $("#wrapwrap > header").removeClass("header_scrolled");
    }
});