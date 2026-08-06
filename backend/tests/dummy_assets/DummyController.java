package com.example.dummy;

public class DummyController {
    public void initForm() {
        System.out.println("Init dummy form");
    }

    public String processSubmit(String input) {
        return "Submitted: " + input;
    }
}
